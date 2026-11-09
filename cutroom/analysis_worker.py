"""Short-lived CPU analysis processes keep Torch/aligner memory out of the web app."""
import argparse
import json
import os
from pathlib import Path

def atomic(path,value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False))
    temporary.replace(path)


def audio_events(wav, output, model_cache):
    import numpy as np
    import torch
    import wave
    from transformers import AutoFeatureExtractor, ASTForAudioClassification
    torch.set_num_threads(4)
    with wave.open(str(wav), "rb") as source:
        rate = source.getframerate()
        values = np.frombuffer(source.readframes(source.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    stride = int(rate * .5)
    energies = np.array([float(np.sqrt(np.mean(values[i:i + stride] ** 2) + 1e-12)) for i in range(0, len(values), stride)])
    peaks = []
    cutoff = max(.015, float(np.percentile(energies, 90))) if len(energies) else 1
    for i in np.argsort(energies)[::-1]:
        at = i * .5
        if energies[i] < cutoff or any(abs(at - p["at"]) < 3 for p in peaks):
            continue
        peaks.append({"at": at, "kind": "energy_peak", "confidence": float(min(1, energies[i] / max(cutoff, .01))), "rms": float(energies[i])})
        if len(peaks) >= 100:
            break
    name = "MIT/ast-finetuned-audioset-10-10-0.4593"
    extractor = AutoFeatureExtractor.from_pretrained(name, cache_dir=model_cache)
    model = ASTForAudioClassification.from_pretrained(name, cache_dir=model_cache).eval()
    labels = {"Laughter", "Giggle", "Snicker", "Shout", "Screaming", "Cheering", "Applause", "Explosion", "Bang", "Crash", "Breaking", "Impact", "Music"}
    record = {"version": 2, "classifier": name, "complete": False, "events": peaks, "windows": 0}
    if output.exists():
        previous = json.loads(output.read_text())
        if previous.get("classifier") == name:
            record = previous
    for i in range(record["windows"], int(np.ceil(len(values) / (rate * 10)))):
        clip = values[i * rate * 10:(i + 1) * rate * 10]
        if len(clip) < rate:
            break
        inputs = extractor(clip, sampling_rate=rate, return_tensors="pt")
        with torch.inference_mode():
            scores = model(**inputs).logits[0].sigmoid()
        for index in scores.topk(8).indices.tolist():
            label, score = model.config.id2label[index], float(scores[index])
            if label in labels and score > .12:
                record["events"].append({"at": i * 10 + len(clip) / rate / 2, "start": i * 10,
                                         "end": i * 10 + len(clip) / rate, "kind": label.lower(), "confidence": score})
        record["windows"] = i + 1
        temporary = output.with_suffix(".tmp")
        temporary.write_text(json.dumps(record))
        temporary.replace(output)
    record["complete"] = True
    atomic(output,record)


def align(wav, input_path, output, cache):
    import torch
    import whisperx
    torch.set_num_threads(4)
    source = json.loads(input_path.read_text())
    language = source["language"]
    model, metadata = whisperx.load_align_model(language_code=language, device="cpu", model_dir=cache,
                                               model_name='facebook/wav2vec2-base-960h' if language=='en' else None)
    audio = whisperx.load_audio(str(wav))
    result = whisperx.align(source["segments"], model, metadata, audio, "cpu", return_char_alignments=False)
    atomic(output,result)


def scenes(video, output):
    from scenedetect import detect, AdaptiveDetector
    found = detect(str(video), AdaptiveDetector(), show_progress=False)
    atomic(output,{"cuts": [a.get_seconds() for a, b in found][1:]})


def retrieve(source, output, cache):
    """CPU-only semantic proposals; the vision scouts still judge real evidence."""
    import numpy as np
    import torch
    from transformers import AutoTokenizer, AutoModel
    torch.set_num_threads(2)
    name='intfloat/multilingual-e5-small'
    tokenizer=AutoTokenizer.from_pretrained(name,cache_dir=cache)
    model=AutoModel.from_pretrained(name,cache_dir=cache).eval().to('cpu')
    segments=json.loads(source.read_text())['segments']
    passages=[]
    for item in segments:
        if passages and item['end']-passages[-1]['start']<=45 and len(passages[-1]['text'])+len(item['text'])<900:
            passages[-1]['end']=item['end'];passages[-1]['text']+=' '+item['text']
        else:
            passages.append({k:item[k] for k in ('start','end','text')})
    queries=['a funny unexpected reaction with a punchline', 'a tense challenge with a surprising outcome',
             'an exciting reveal that answers a question', 'an emotional moment and what caused it',
             'an impressive visual or gameplay surprise', 'an interesting story with a clear ending']
    def encode(texts):
        result=[]
        for offset in range(0,len(texts),8):
            inputs=tokenizer(texts[offset:offset+8],max_length=512,padding=True,truncation=True,return_tensors='pt')
            with torch.inference_mode():
                hidden=model(**inputs).last_hidden_state
                mask=inputs['attention_mask'].unsqueeze(-1)
                pooled=(hidden*mask).sum(1)/mask.sum(1).clamp(min=1)
                result.append(torch.nn.functional.normalize(pooled,p=2,dim=1).cpu().numpy())
        return np.concatenate(result) if result else np.empty((0,384))
    query_vectors=encode(['query: '+q for q in queries])
    embeddings=encode(['passage: '+p['text'] for p in passages])
    scores=(embeddings@query_vectors.T).max(axis=1) if passages else []
    atomic(output,{'model':name,'revision':getattr(model.config,'_commit_hash',None),'device':'cpu',
                   'passages':[{'start':p['start'],'end':p['end'],'score':round(float(score),4)} for p,score in zip(passages,scores)]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task", choices=["audio", "align", "scenes", "retrieve", "prepare-audio","prepare-align"])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    os.environ["HF_HOME"] = str(args.cache)
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    nltk_cache=args.cache/'nltk'
    nltk_cache.mkdir(parents=True,exist_ok=True)
    os.environ['NLTK_DATA']=str(nltk_cache.resolve())
    if args.task == "audio":
        audio_events(args.source, args.output, str(args.cache))
    elif args.task == "align":
        align(args.source, args.input, args.output, str(args.cache))
    elif args.task == "scenes":
        scenes(args.source, args.output)
    elif args.task == 'retrieve':
        retrieve(args.source,args.output,str(args.cache))
    elif args.task=='prepare-audio':
        from transformers import AutoFeatureExtractor, ASTForAudioClassification
        name = "MIT/ast-finetuned-audioset-10-10-0.4593"
        AutoFeatureExtractor.from_pretrained(name, cache_dir=str(args.cache))
        ASTForAudioClassification.from_pretrained(name, cache_dir=str(args.cache))
        print("Audio-event classifier downloaded.")
    else:
        import nltk
        from transformers import Wav2Vec2Processor,Wav2Vec2ForCTC
        name='facebook/wav2vec2-base-960h'
        Wav2Vec2Processor.from_pretrained(name,cache_dir=str(args.cache))
        Wav2Vec2ForCTC.from_pretrained(name,cache_dir=str(args.cache))
        nltk.download('punkt_tab',download_dir=str(nltk_cache),quiet=True,raise_on_error=True)
        atomic(args.cache.parent.parent/'alignment-en-ready.json',{'model':name,'device':'cpu','download_cache':'huggingface'})
        print('English forced-alignment model and tokenizer prepared.')


if __name__ == "__main__":
    main()

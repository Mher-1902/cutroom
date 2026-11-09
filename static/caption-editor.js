'use strict';
// This editor changes a saved plan; it never starts another analysis run.
window.CutroomCaptionEditor = (() => {
  const presets = {
    focus: {font:'sans',size:82,accent:'#B5FF73',max_words:3,case:'preserve',position:'auto',animation:'highlight'},
    clean: {font:'studio',size:78,accent:'#FFFFFF',max_words:4,case:'preserve',position:'auto',animation:'fade'},
    punch: {font:'sans',size:88,accent:'#FFD65C',max_words:2,case:'uppercase',position:'auto',animation:'highlight'}
  };
  function init({api,toast,currentJob,onQueued}) {
    const el=id=>document.getElementById(id), dialog=el('caption-dialog');
    let current=null,jobId=null;
    function read() {
      return {preset:el('edit-caption-preset').value,font:el('edit-caption-font').value,
        size:Number(el('edit-caption-size').value),accent:el('edit-caption-color').value.toUpperCase(),
        max_words:Number(el('edit-caption-words').value),case:el('edit-caption-case').value,
        position:el('edit-caption-position').value,animation:el('edit-caption-animation').value};
    }
    function sample() {
      const p=read(), box=el('caption-sample'), line=el('caption-sample-line');
      box.dataset.font=p.font; box.dataset.case=p.case;
      line.style.fontSize=`${p.size/3}px`;
      el('caption-sample-accent').style.color=p.accent;
      el('caption-size-value').textContent=`${p.size}px`;
    }
    function fill(p) {
      for(const [id,key] of [['preset','preset'],['font','font'],['size','size'],['color','accent'],['words','max_words'],['case','case'],['position','position'],['animation','animation']])el('edit-caption-'+id).value=p[key];
      sample();
    }
    el('clips-grid').addEventListener('click',async event=>{
      const button=event.target.closest('[data-style]');if(!button)return;
      button.disabled=true;
      try {
        const job=currentJob();jobId=job.id;
        current=await api(`/api/jobs/${jobId}/clips/${button.dataset.style}/editor`);
        fill(current.caption_settings);
        el('caption-edit-title').textContent=job.clips.find(c=>c.id===current.clip_id).title;
        el('caption-current-video').src=current.video;
        el('edit-caption-hook').value=current.hook_text;
        el('edit-caption-enabled').checked=current.caption_enabled;
        el('edit-caption-layout').value='keep';el('edit-caption-focus').value=current.focus_x;
        el('caption-focus-control').hidden=true;
        const fragment=document.createDocumentFragment();
        for(const word of current.words){
          const label=document.createElement('label'), time=document.createElement('span'), input=document.createElement('input');
          time.textContent=`${Math.floor(word.start/60)}:${String(Math.floor(word.start%60)).padStart(2,'0')}`;
          input.value=word.text;input.maxLength=60;input.required=true;input.dataset.wordId=word.id;input.setAttribute('aria-label',`Caption at ${time.textContent}: ${word.text}`);
          label.append(time,input);fragment.append(label);
        }
        el('caption-word-list').replaceChildren(fragment);
        dialog.showModal();
      } catch(error) {toast(error.message);} finally {button.disabled=false;}
    });
    el('close-caption-editor').addEventListener('click',()=>dialog.close());
    dialog.addEventListener('close',()=>el('caption-current-video').pause());
    el('edit-caption-preset').addEventListener('change',()=>{const preset=el('edit-caption-preset').value;fill({preset,...presets[preset]});});
    el('caption-style-controls').addEventListener('input',sample);
    el('edit-caption-layout').addEventListener('change',()=>el('caption-focus-control').hidden=el('edit-caption-layout').value!=='crop');
    el('save-caption-preset').addEventListener('click',()=>{
      try{localStorage.setItem('cutroom-caption-preset',JSON.stringify(read()));toast('Style saved. Choose ‘My saved style’ for new projects.');}
      catch{toast('This browser could not save the preset.');}
    });
    el('load-caption-preset').addEventListener('click',()=>{
      try{const saved=JSON.parse(localStorage.getItem('cutroom-caption-preset'));if(!saved)throw Error();fill(saved);}
      catch{toast('Save a style first.');}
    });
    el('caption-edit-form').addEventListener('submit',async event=>{
      event.preventDefault();const button=el('render-caption-style');button.disabled=true;
      try {
        const originals=new Map(current.words.map(w=>[w.id,w.text]));const edits={};
        for(const input of el('caption-word-list').querySelectorAll('input'))if(input.value.trim()!==originals.get(input.dataset.wordId))edits[input.dataset.wordId]=input.value.trim();
        const job=await api(`/api/jobs/${jobId}/clips/${current.clip_id}/style`,{
          revision:current.revision,caption_settings:read(),caption_edits:edits,caption_enabled:el('edit-caption-enabled').checked,
          layout:el('edit-caption-layout').value,focus_x:Number(el('edit-caption-focus').value),hook_text:el('edit-caption-hook').value.trim()});
        onQueued(job);dialog.close();toast('Rendering the new style. Your existing export stays available.');
      } catch(error) {toast(error.message);} finally {button.disabled=false;}
    });
  }
  function creationSettings(preset) {
    if(preset==='saved'){
      try{return JSON.parse(localStorage.getItem('cutroom-caption-preset'))||{preset:'focus'};}catch{return {preset:'focus'};}
    }
    return {preset:preset==='none'?'focus':preset};
  }
  return {init,creationSettings};
})();

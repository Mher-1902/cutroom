"""Build OFL caption instances; renamed families respect reserved font names.

Run with the analysis environment, which includes fontTools. Source fonts and
their OFL licenses are bundled; rendering never downloads or builds fonts.
"""
import hashlib
import json
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT=Path(__file__).resolve().parents[1]/'static/fonts'


def build(source,target,family,weight,axes):
    original=TTFont(ROOT/source,recalcTimestamp=False)
    font=instantiateVariableFont(original,axes,inplace=False)
    font.recalcTimestamp=False
    label='ExtraBold' if weight==800 else 'Bold'
    replacements={1:family,2:label,3:family.replace(' ','')+'-'+label+'-1.0',
                  4:family+' '+label,6:family.replace(' ','')+'-'+label,16:family,17:label}
    for record in list(font['name'].names):
        if record.nameID in replacements:
            font['name'].setName(replacements[record.nameID],record.nameID,record.platformID,record.platEncID,record.langID)
    font['OS/2'].usWeightClass=weight
    font['OS/2'].fsSelection=(font['OS/2'].fsSelection | (1<<5)) & ~(1<<6)
    font['head'].macStyle |= 1
    path=ROOT/'captions'/target
    font.save(path)
    return {'family':family,'path':'captions/'+target,'kind':'font','license':'OFL-1.1',
            'derived_from':source,'axes':axes,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'purpose':'Renamed static OFL instance for reliable FFmpeg/libass and browser preview'}


def main():
    assets=[build('montserrat/Montserrat-Variable.ttf','CutroomSans-ExtraBold.ttf','Cutroom Sans',800,{'wght':800}),
            build('instrumentsans/InstrumentSans-Variable.ttf','CutroomStudio-Bold.ttf','Cutroom Studio',700,{'wght':700,'wdth':100})]
    manifest=ROOT/'manifest.json';record=json.loads(manifest.read_text())
    replaced={a['path'] for a in assets}
    sources=[('montserrat/Montserrat-Variable.ttf','font','https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf'),
             ('montserrat/OFL.txt','license','https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/OFL.txt')]
    for name,kind,url in sources:
        replaced.add(name)
        assets.append({'family':'montserrat','path':name,'kind':kind,'license':'OFL-1.1','source_url':url,
                       'sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest()})
    record['assets']=[a for a in record['assets'] if a['path'] not in replaced]+assets
    manifest.write_text(json.dumps(record,indent=2)+'\n')
    print('Bundled two modern caption families with source fonts, checksums and OFL licenses.')


if __name__=='__main__':main()

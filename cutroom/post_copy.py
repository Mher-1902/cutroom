"""Post-copy validation shared by generated plans and publication exports."""
import re
import unicodedata

MAX_CHARACTERS = 159
TONES = {'funny','dramatic','suspenseful','surprising','impressive','informative','emotional','mixed'}


def caption(value):
    text=unicodedata.normalize('NFC',re.sub(r'\s+',' ',str(value)).strip())
    if len(text)>MAX_CHARACTERS:
        raise ValueError('Post caption must be shorter than 160 characters, including spaces and hashtags.')
    return text

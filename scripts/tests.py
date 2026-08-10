"""
Проверка: данные загружаются, пути к аудио существуют, функции возвращают результат.
Запуск: python scripts/tests.py
Результат: data/test_result.txt (рядом с данными проекта)
"""

import json, os, sys

# Корень проекта = родитель папки scripts
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errors = []
log = []

def check(ok, msg):
    if not ok:
        errors.append(f'FAIL: {msg}')
        log.append(f'  FAIL {msg}')
    else:
        log.append(f'  OK   {msg}')

# 1. alphabet.json
print('\n[alphabet.json]')
data = json.load(open(os.path.join(BASE, 'data', 'alphabet.json'), 'r', encoding='utf-8'))
check(len(data['letters']) == 31, f'31 letters, got {len(data["letters"])}')

for l in data['letters']:
    lid = l['id']
    check(1 <= lid <= 31, f'id={lid} in range')
    check(l['letter'], f'id={lid} has letter')
    check(l['name_en'], f'id={lid} has name_en')
    check(l.get('audio_file'), f'id={lid} has audio_file field')

# audio files exist
for l in data['letters']:
    af = l.get('audio_file', '')
    if af:
        full = os.path.join(BASE, 'assets', 'audio', af)
        check(os.path.exists(full), f'audio {af} exists')

# 2. words.json
print('\n[words.json]')
data2 = json.load(open(os.path.join(BASE, 'data', 'words.json'), 'r', encoding='utf-8'))
check(len(data2['words']) > 0, f'{len(data2["words"])} words')

for w in data2['words'][:3]:
    check(w.get('he'), f'word has he: {w["he"]}')
    check(w.get('ru'), f'word has ru')
    check(w.get('audio_file'), f'word has audio_file')
    check(w.get('letter'), f'word has letter')
    check(w.get('level') == 1, f'word level is 1')

# audio files for a few words
for w in data2['words'][:5]:
    af = w.get('audio_file', '')
    full = os.path.join(BASE, 'assets', 'audio', 'words', af)
    check(os.path.exists(full), f'word audio {af} exists')

# 3. Logic functions
print('\n[logic]')
sys.path.insert(0, BASE)
from utils.logic import get_all_letters, get_letter_by_id, get_word_for_level, get_quiz_sound_to_letter, get_quiz_letter_to_sound

check(len(get_all_letters()) == 31, 'get_all_letters returns 31')
check(get_letter_by_id(1) is not None, 'get_letter_by_id(1) works')
w = get_word_for_level()
check(w is not None, 'get_word_for_level returns word')
if w:
    check(len(w['he']) <= 3, f'word {w["he"]} is <=3 letters')

q = get_quiz_sound_to_letter()
check(q is not None, 'get_quiz_sound_to_letter works')
check('correct' in q, 'quiz has correct')
check('options' in q, 'quiz has options')

q2 = get_quiz_letter_to_sound()
check(q2 is not None, 'get_quiz_letter_to_sound works')

# 4. Bot imports
print('\n[bot imports]')
try:
    import utils.database
    check(True, 'database imports OK')
    import utils.tts
    check(True, 'tts imports OK')
except Exception as e:
    check(False, f'import error: {e}')

# Summary
result_path = os.path.join(BASE, 'data', 'test_result.txt')
with open(result_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(log) + '\n\n')
    f.write('='*40 + '\n')
    if errors:
        f.write(f'FAILED: {len(errors)} checks failed\n')
        for e in errors:
            f.write(f'  {e}\n')
    else:
        f.write('ALL CHECKS PASSED\n')
print(f'Results written to {result_path}')

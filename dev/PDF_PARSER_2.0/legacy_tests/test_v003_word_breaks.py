#!/usr/bin/env python3
"""Check v003 output for mid-word breaks."""
import fitz

doc = fitz.open('runtime/output/docx/v003/layout/Соглашение_о_расторжении_ИП_Смирнов_docx_en.pdf')
page = doc[0]
text = page.get_text('text')

print('=' * 80)
print('🔍 CHECKING FOR MID-WORD BREAKS (v003 with word boundary fix)')
print('=' * 80)
print()
print('Full text (first 800 chars):')
print('-' * 80)
print(text[:800])
print()
print('=' * 80)
print('SEARCHING FOR KNOWN BREAK PATTERNS:')
print('=' * 80)

# Check for specific breaks that were present in v002
expressio_found = 'EXPRESSIO' in text
date_break = '202\n3' in text
dept_break = 'Departme\nnt' in text
pers_break = 'natural pers\n' in text

print(f"  'EXPRESSIO' (broken 'TERMINATION'): {'❌ FOUND' if expressio_found else '✅ NOT FOUND'}")
print(f"  '202' + newline + '3' (broken '2023'): {'❌ FOUND' if date_break else '✅ NOT FOUND'}")
print(f"  'Departme' + newline + 'nt' (broken 'Department'): {'❌ FOUND' if dept_break else '✅ NOT FOUND'}")
print(f"  'natural pers' + newline (broken 'person'): {'❌ FOUND' if pers_break else '✅ NOT FOUND'}")
print()

# Check for correct full words
termination_found = 'TERMINATION' in text
department_found = 'Department' in text
year_2023 = '2023' in text

print('=' * 80)
print('CHECKING FOR COMPLETE WORDS:')
print('=' * 80)
print(f"  'TERMINATION' (complete): {'✅ FOUND' if termination_found else '❌ NOT FOUND'}")
print(f"  'Department' (complete): {'✅ FOUND' if department_found else '❌ NOT FOUND'}")
print(f"  '2023' (complete): {'✅ FOUND' if year_2023 else '❌ NOT FOUND'}")
print()

print('Full title (first 5 lines):')
print('-' * 80)
lines = text.split('\n')
for i, line in enumerate(lines[:5]):
    print(f'{i+1}. {line}')

print()
print('=' * 80)
print('📋 SUMMARY:')
print('=' * 80)

all_good = not (expressio_found or date_break or dept_break or pers_break)
all_complete = termination_found and year_2023

if all_good and all_complete:
    print('✅ SUCCESS: All mid-word breaks are FIXED!')
    print('   • No broken words detected')
    print('   • All expected complete words found')
else:
    print('⚠️  ISSUES DETECTED:')
    if not all_good:
        print('   • Some mid-word breaks still present')
    if not all_complete:
        print('   • Some expected complete words missing')

doc.close()

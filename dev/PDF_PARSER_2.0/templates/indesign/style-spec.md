
# InDesign мастер-шаблон (Style Spec)

Документ:
- Формат: A4, поля 22 мм, базовая сетка 12 pt.
- Главный стиль текста: Source Serif 4 (или Noto Serif), 11 pt / 14 pt.
- Заголовки (Paragraph Styles):
  - H1: Source Sans 3 (или Noto Sans), 18 pt / 22 pt, перед 12 pt, после 6 pt.
  - H2: 14 pt / 18 pt, перед 10 pt, после 4 pt.
  - H3: 12 pt / 16 pt, перед 8 pt, после 2 pt.
- Текст (Body): 11/14, Tracking 0.
- Списки: List Bullet, List Numbered (отступ 6 мм).
- Подпись к рисунку (Figure Caption): 9/12, курсив, перед 4 pt.
- Таблица (Table Style): таблицы шириной в колонку, верх/низ: 6 pt, межколонник 6 pt.
- Языковые словари: Russian, English: UK, French: France. Composer: World-Ready.

Object Styles:
- Figure Inline: Anchored to text, текстовая привязка «Inline», выравнивание по центру, макс. ширина 85% колонки.
- Table Block: объект с Text Wrap: 0, таблица внутри TexFrame, Caption ниже.

Anchoring:
- Все изображения и схемы вставляются только как Anchored Objects, чтобы сохранять положение при изменении языка.

Версионирование:
- Layer «Text RU/EN/FR» запрещено — язык меняется через импорт XLIFF/IDML, а не слоями.

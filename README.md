# 📈 בוט Paper-Trading — מניות ישראליות ואמריקאיות

בוט מסחר בסימולציה (paper trading) שעוקב אחרי מניות אמריקאיות (NASDAQ/NYSE)
ומניות ישראליות (TASE) יחד, מייצר איתותים לפי אינדיקטורים טכניים + סנטימנט
חדשות אופציונלי, מבצע עסקאות בתיק וירטואלי, ומנהל סיכונים.

> ⚠️ **זו סימולציה בלבד, ואין כאן ייעוץ השקעות.** הבוט לא מחובר לכסף אמיתי.
> תוצאות backtest אינן הבטחה לעתיד. לעולם אל תעבור לכסף אמיתי לפני שהוכחת
> אסטרטגיה לאורך זמן ב-backtest וב-paper trading.

## התקנה

```bash
pip install -r requirements.txt
```

## שימוש

```bash
python main.py backtest   # בדיקה היסטורית של האסטרטגיה על כל היוניברס
python main.py run        # הרצת paper-trading אחת (שומרת מצב בין הרצות)
python main.py status     # הצגת מצב התיק הנוכחי
python main.py reset      # איפוס התיק
```

להרצה יומית אוטומטית אחרי סגירת המסחר (cron, למשל 23:10):

```cron
10 23 * * 1-5  cd /path/to/trading_bot && /usr/bin/python3 main.py run >> bot.log 2>&1
```

## מבנה הפרויקט

```
trading_bot/
├── main.py              # CLI: run / backtest / status / reset
├── config.py            # יוניברס, הון, פרמטרים — ערוך כאן
├── requirements.txt
├── bot/
│   ├── data.py          # שליפת מחירים (yfinance), טיפול ב-TASE/אגורות ומטבע
│   ├── indicators.py    # SMA, EMA, RSI, MACD, ATR — פונקציות טהורות
│   ├── strategy.py      # מנוע איתותים (TrendMomentum)
│   ├── portfolio.py     # סימולציית ברוקר: מזומן, פוזיציות, עמלות, P&L
│   ├── risk.py          # גודל פוזיציה ו-stop/target
│   ├── backtest.py      # backtester + מדדי ביצוע
│   ├── sentiment.py     # ציון סנטימנט מחדשות (אופציונלי, ניתן להחלפה)
│   ├── dashboard.py     # ייצוא JSON לדשבורד
│   └── runner.py        # לולאת paper-trading חיה
├── webapp/              # דשבורד PWA (פרוס ל-Netlify / GitHub Pages)
│   ├── index.html       # הדשבורד עצמו
│   ├── manifest.webmanifest
│   ├── sw.js            # service worker (מסך בית / אופליין)
│   ├── dashboard.json   # נתוני התיק (מתעדכן ע"י הבוט)
│   └── icon-*.png
├── .github/workflows/
│   └── paper-trade.yml  # תזמון יומי בענן (GitHub Actions)
└── tests/
    └── test_core.py     # בדיקות ללוגיקה הטהורה (דאטה סינתטי, ללא רשת)
```

## האסטרטגיה (ברירת מחדל)

`TrendMomentumStrategy` — שילוב מגמה + מומנטום:
- **מסנן מגמה:** קונים רק כשהמחיר מעל SMA-200.
- **כניסה:** חציית MACD מעל קו הסיגנל, כש-RSI לא בקנייתֿ-יתר.
- **יציאה:** חציית MACD מתחת לסיגנל, או RSI מעל 75, או סטופ/יעד.
- **סנטימנט (אופציונלי):** הפעל `use_sentiment=True` ב-`config.py` כדי
  לסנן קניות כשחדשות הסימבול שליליות.

זו **נקודת התחלה**, לא אסטרטגיה מנצחת. החלף בקלות: צור מחלקה שיורשת מ-
`Strategy` וממש `generate_signals`.

## נקודות חשובות

- **TASE באגורות:** הרבה מניות ישראליות מצוטטות ב-Yahoo באגורות (1/100 ₪).
  `data.py` ממיר אוטומטית לשקלים. ודא שהמחירים נראים הגיוניים.
- **מטבע:** התיק מתנהל ב-USD; פוזיציות TASE מומרות לפי שער ILS=X חי.
- **ה-backtester פשוט:** אין slippage/פערי פתיחה/נזילות. המציאות קשה יותר.

## 📱 הרצה ותצוגה על האייפון

הבוט רץ בענן (בחינם, דרך GitHub Actions) והאייפון מציג דשבורד PWA ממסך
הבית. ככה iOS לא צריך להריץ כלום ברקע — הוא רק *מציג*.

**שלב 1 — העלאה ל-GitHub.** צור repo חדש ודחוף אליו את כל התיקייה.

**שלב 2 — הפעלת התזמון.** ב-repo: לשונית **Actions** → אשר הרצת workflows.
ה-workflow (`.github/workflows/paper-trade.yml`) רץ אוטומטית בימי מסחר ב-21:30
UTC. להרצה ראשונה מיידית: Actions → *paper-trade* → **Run workflow**.
זה מייצר את `webapp/dashboard.json` ודוחף אותו חזרה.

**שלב 3 — פרסום הדשבורד.** פרוס את תיקיית `webapp/` כאתר סטטי:
- **Netlify:** New site from Git → Publish directory: `webapp` → Deploy.
- או **GitHub Pages:** Settings → Pages → Deploy from branch → `/webapp`.

מכיוון ש-`dashboard.json` יושב בתוך `webapp/`, הדשבורד קורא אותו מאותו
origin בלי CORS. בכל הרצת בוט הקובץ מתעדכן והאתר נפרס מחדש אוטומטית.

**שלב 4 — הוספה למסך הבית.** באייפון, פתח את כתובת האתר ב-**Safari** →
כפתור השיתוף → **הוספה למסך הבית**. עכשיו יש לך אייקון שנפתח כאפליקציה
במסך מלא, ומציג את התיק — מתעדכן כל יום לבד.

> רוצה לנתק את התצוגה מהפריסה? ב-`webapp/index.html` שנה את `DATA_URL`
> ל-URL הגולמי של הקובץ ב-GitHub. אז כל commit של הבוט יתעדכן בדשבורד
> בלי פריסה מחדש.

### למה לא להריץ את הפייתון *ישירות* על האייפון?
אפשר (למשל עם Pyto, שכוללת pandas/numpy) — אבל iOS לא מריץ סקריפט יומי
ברקע בצורה אמינה, אז היית צריך ללחוץ "הרץ" ידנית בכל יום. הגישה כאן נותנת
הרצה יומית אמינה *וגם* תצוגה נוחה מהאייפון.

## הצעדים הבאים האפשריים

1. הרץ `backtest` והסתכל על Max Drawdown ו-Sharpe, לא רק על התשואה.
2. שפר את האסטרטגיה ובדוק מחדש (היזהר מ-overfitting!).
3. צבור היסטוריית paper לכמה שבועות לפני שאתה סומך על משהו.
4. רק אז שקול ברוקר אמיתי (למשל Interactive Brokers API) — בזהירות רבה.

## בדיקות

```bash
python -m tests.test_core
```

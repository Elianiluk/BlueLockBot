# בוט טלגרם – פרקים חדשים של Blue Lock

הבוט בודק כל 30 דקות את [Blue Lock ב-WeebCentral](https://weebcentral.com/series/01J76XYD7E91K8QP6CY0Y53900/Blue-Lock).
כשעולה פרק חדש, הוא שולח לך הודעה בטלגרם עם לינק לפרק.
הבוט רץ בחינם על GitHub Actions, כך שהמחשב לא צריך להיות דלוק.

## הקמה (פעם אחת, בערך 5 דקות)

### 1. יצירת בוט בטלגרם
1. בטלגרם פתח את **@BotFather** ושלח `/newbot`.
2. בחר לבוט שם ושם משתמש שנגמר ב-`bot` (למשל `my_bluelock_bot`).
3. BotFather ישלח לך **token** שנראה בערך כך: `123456:ABC-...`. שמור אותו ואל תשתף אותו עם אף אחד.
4. פתח את הבוט החדש ושלח לו `/start`. בלי השלב הזה הוא לא יוכל לשלוח לך הודעות.

### 2. העלאה ל-GitHub
1. ב-GitHub צור repository חדש. הוא יכול להיות **Private**.
2. העלה אליו את כל הקבצים מהתיקייה הזו, כולל התיקייה `.github` (Add file → Upload files, ואז גרור את כל התוכן).

### 3. שמירת ה-token
ב-repository היכנס ל-**Settings → Secrets and variables → Actions → New repository secret**:
- Name: `TELEGRAM_TOKEN`
- Secret: ה-token מ-BotFather

### 4. הפעלה ראשונה
עבור ללשונית **Actions**. אם GitHub מבקש לאשר workflows, אשר. אחר כך בחר **Check Blue Lock chapters → Run workflow**.
תוך דקה אמורה להגיע אליך הודעה: "✅ הבוט פעיל! הפרק האחרון...".

מהרגע הזה ההודעות יגיעו לבד.

## הערות
- הבדיקה מתבצעת בערך כל 30 דקות. GitHub לפעמים מעכב הרצות מתוזמנות בכמה דקות.
- אם ריצה נכשלת, GitHub ישלח לך מייל. הסיבה הסבירה היא שהאתר שינה את המבנה שלו.
- `state.json` שומר את הפרק האחרון שעליו קיבלת הודעה. הבוט מעדכן אותו לבד.

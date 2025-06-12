import sqlite3

# الاتصال بقاعدة البيانات (سيتم إنشاؤها إذا لم تكن موجودة)
conn = sqlite3.connect('cv_database.db')
cursor = conn.cursor()

# إنشاء جدول لتخزين معلومات السيرة الذاتية
cursor.execute('''
    CREATE TABLE IF NOT EXISTS cvs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT,
        education TEXT,
        experience TEXT,
        skills TEXT,
        image_filename TEXT
    )
''')

print("تم إنشاء الجدول بنجاح!")

# حفظ التغييرات وإغلاق الاتصال
conn.commit()
conn.close()
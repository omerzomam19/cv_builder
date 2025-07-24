from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import uuid # لاستخدامها في توليد أسماء ملفات فريدة

# ===============================================
# 1. إعدادات التطبيق
# ===============================================
app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'} # أضفنا PDF للشهادات

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_super_secret_key_here' 

db = SQLAlchemy(app)

# ===============================================
# 2. تعريف نماذج قاعدة البيانات
# ===============================================
class CV(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    date_of_birth = db.Column(db.Date)
    linkedin_profile = db.Column(db.String(255))
    github_profile = db.Column(db.String(255))
    education = db.Column(db.Text)
    experience = db.Column(db.Text)
    skills = db.Column(db.Text)
    image_filename = db.Column(db.String(255)) # اسم ملف الصورة الشخصية

    # علاقة One-to-Many لصور الشهادات
    # 'certificate_images' هو اسم المتغير الذي سنستخدمه للوصول إلى صور الشهادات من كائن CV
    # backref='cv' يعني أنه يمكننا الوصول إلى كائن CV من كائن CertificateImage
    # lazy=True تعني أن الصور لن يتم تحميلها إلا عند الحاجة (أداء أفضل)
    # cascade='all, delete-orphan' يعني عند حذف CV، سيتم حذف جميع صور الشهادات المرتبطة بها
    certificate_images = db.relationship('CertificateImage', backref='cv', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<CV {self.full_name}>'

class CertificateImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cv_id = db.Column(db.Integer, db.ForeignKey('cv.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    # يمكن إضافة حقول أخرى هنا مثل 'title' أو 'description' للشهادة
    title = db.Column(db.String(100), default='شهادة')

    def __repr__(self):
        return f'<CertificateImage {self.filename}>'

# ===============================================
# 3. وظيفة مساعدة للتحقق من امتداد الملفات
# ===============================================
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ===============================================
# 4. مسارات التطبيق (Routes)
# ===============================================

# الصفحة الرئيسية - عرض جميع السير الذاتية
@app.route('/')
def index():
    cvs = CV.query.order_by(CV.full_name).all()
    return render_template('index.html', cvs=cvs)

# إنشاء سيرة ذاتية جديدة
@app.route('/create_cv', methods=['GET', 'POST'])
def create_cv():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        
        date_of_birth_str = request.form['date_of_birth']
        date_of_birth = None
        if date_of_birth_str:
            try:
                date_of_birth = datetime.strptime(date_of_birth_str, '%Y-%m-%d').date()
            except ValueError:
                flash('صيغة تاريخ الميلاد غير صحيحة. يرجى استخدام YYYY-MM-DD.', 'danger')
                return redirect(request.url)
        
        linkedin_profile = request.form.get('linkedin_profile', '')
        github_profile = request.form.get('github_profile', '')

        education = request.form['education']
        experience = request.form['experience']
        skills = request.form['skills']
        image_filename = None

        # معالجة الصورة الشخصية (سحب وإفلات أو رفع عادي)
        if 'profile_image' in request.files and request.files['profile_image'].filename != '':
            file = request.files['profile_image']
            if file and allowed_file(file.filename):
                # توليد اسم ملف فريد
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                if not os.path.exists(app.config['UPLOAD_FOLDER']):
                    os.makedirs(app.config['UPLOAD_FOLDER'])
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename
            else:
                flash('امتداد الصورة الشخصية غير مسموح به.', 'warning')
                return redirect(request.url)

        new_cv = CV(
            full_name=full_name,
            email=email,
            phone=phone,
            address=address,
            date_of_birth=date_of_birth,
            linkedin_profile=linkedin_profile,
            github_profile=github_profile,
            education=education,
            experience=experience,
            skills=skills,
            image_filename=image_filename
        )
        db.session.add(new_cv)
        db.session.commit() # commit هنا لحفظ CV أولاً للحصول على cv.id

        # معالجة صور الشهادات المتعددة
        if 'certificate_files' in request.files:
            certificate_files = request.files.getlist('certificate_files')
            certificate_titles = request.form.getlist('certificate_titles') # احصل على العناوين
            
            for i, file in enumerate(certificate_files):
                if file and allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = f"{uuid.uuid4()}.{ext}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    
                    # احصل على العنوان الخاص بهذه الشهادة (إذا كان موجوداً)
                    title = certificate_titles[i] if i < len(certificate_titles) else 'شهادة'
                    
                    cert_image = CertificateImage(cv_id=new_cv.id, filename=filename, title=title)
                    db.session.add(cert_image)
                elif file.filename != '': # إذا كان هناك ملف ولكن امتداده غير مسموح به
                    flash(f'امتداد ملف الشهادة "{file.filename}" غير مسموح به.', 'warning')
        
        db.session.commit() # commit مرة أخرى لحفظ صور الشهادات

        flash('تم إنشاء السيرة الذاتية بنجاح!', 'success')
        return redirect(url_for('index'))
    return render_template('create_cv.html')

# عرض سيرة ذاتية محددة
@app.route('/cv/<int:cv_id>')
def view_cv(cv_id):
    cv = CV.query.get_or_404(cv_id)
    return render_template('cv_template.html', cv=cv)

# تعديل سيرة ذاتية موجودة
@app.route('/edit_cv/<int:cv_id>', methods=['GET', 'POST'])
def edit_cv(cv_id):
    cv = CV.query.get_or_404(cv_id)
    if request.method == 'POST':
        cv.full_name = request.form['full_name']
        cv.email = request.form['email']
        cv.phone = request.form['phone']
        cv.address = request.form['address']
        
        date_of_birth_str = request.form['date_of_birth']
        if date_of_birth_str:
            try:
                cv.date_of_birth = datetime.strptime(date_of_birth_str, '%Y-%m-%d').date()
            except ValueError:
                flash('صيغة تاريخ الميلاد غير صحيحة. يرجى استخدام YYYY-MM-DD.', 'danger')
                return redirect(request.url)
        else:
            cv.date_of_birth = None
            
        cv.linkedin_profile = request.form.get('linkedin_profile', '')
        cv.github_profile = request.form.get('github_profile', '')
            
        cv.education = request.form['education']
        cv.experience = request.form['experience']
        cv.skills = request.form['skills']

        # معالجة الصورة الشخصية الجديدة أو حذف الموجودة
        # إذا تم رفع ملف جديد للصورة الشخصية
        if 'profile_image' in request.files and request.files['profile_image'].filename != '':
            file = request.files['profile_image']
            if file and allowed_file(file.filename):
                # حذف الصورة القديمة إذا وجدت
                if cv.image_filename:
                    old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], cv.image_filename)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                cv.image_filename = filename
            else:
                flash('امتداد الصورة الشخصية الجديدة غير مسموح به.', 'warning')
                return redirect(request.url)
        
        # التعامل مع خيار حذف الصورة الشخصية
        if request.form.get('clear_profile_image') == 'on':
            if cv.image_filename:
                old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], cv.image_filename)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
                cv.image_filename = None
                flash('تم حذف الصورة الشخصية بنجاح.', 'info')

        # معالجة صور الشهادات الموجودة (تحديث العناوين وحذف الصور)
        # سيتم إرسال معرفات الصور التي يجب حذفها
        certs_to_delete_ids = request.form.getlist('delete_certificate_ids')
        for cert_id in certs_to_delete_ids:
            cert_to_delete = CertificateImage.query.get(int(cert_id))
            if cert_to_delete and cert_to_delete.cv_id == cv.id: # تأكد أنها تابعة لهذه السيرة الذاتية
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], cert_to_delete.filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                db.session.delete(cert_to_delete)
                flash(f'تم حذف الشهادة {cert_to_delete.title}.', 'info')
        
        # تحديث عناوين الشهادات الموجودة
        # يتم إرسال أزواج id-title من النموذج
        for key, value in request.form.items():
            if key.startswith('certificate_title_'):
                cert_id = key.replace('certificate_title_', '')
                try:
                    cert_id = int(cert_id)
                    cert_image = CertificateImage.query.get(cert_id)
                    if cert_image and cert_image.cv_id == cv.id:
                        cert_image.title = value
                except ValueError:
                    pass # تخطي إذا لم يكن المعرف رقمًا

        # معالجة صور الشهادات الجديدة المضافة
        if 'new_certificate_files' in request.files:
            new_certificate_files = request.files.getlist('new_certificate_files')
            new_certificate_titles = request.form.getlist('new_certificate_titles') # احصل على العناوين الجديدة

            for i, file in enumerate(new_certificate_files):
                if file and allowed_file(file.filename):
                    ext = file.filename.rsplit('.', 1)[1].lower()
                    filename = f"{uuid.uuid4()}.{ext}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    
                    title = new_certificate_titles[i] if i < len(new_certificate_titles) else 'شهادة'
                    
                    cert_image = CertificateImage(cv_id=cv.id, filename=filename, title=title)
                    db.session.add(cert_image)
                elif file.filename != '':
                    flash(f'امتداد ملف الشهادة الجديد "{file.filename}" غير مسموح به.', 'warning')


        db.session.commit()
        flash('تم تحديث السيرة الذاتية بنجاح!', 'success')
        return redirect(url_for('view_cv', cv_id=cv.id))
    return render_template('edit_cv.html', cv=cv)


# حذف سيرة ذاتية
@app.route('/delete_cv/<int:cv_id>', methods=['POST'])
def delete_cv(cv_id):
    cv = CV.query.get_or_404(cv_id)
    
    # حذف الصورة الشخصية المرتبطة
    if cv.image_filename:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], cv.image_filename)
        if os.path.exists(image_path):
            os.remove(image_path)
            
    # حذف جميع صور الشهادات المرتبطة (يتم التعامل معها تلقائيًا بواسطة cascade='all, delete-orphan')
    # ولكن من الأفضل حذف الملفات الفعلية من مجلد الرفع
    for cert_img in cv.certificate_images:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], cert_img.filename)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(cv)
    db.session.commit()
    flash('تم حذف السيرة الذاتية بنجاح!', 'success')
    return redirect(url_for('index'))

# ===============================================
# 5. تشغيل التطبيق
# ===============================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000)


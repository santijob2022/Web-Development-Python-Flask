from flask import Flask,abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap4
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
from dotenv import load_dotenv
import os

load_dotenv()

# Decorator that alllows only the admin access certain routes manually
def admin_only(f):
    @wraps(f)
    def wrapped_function(*args,**kwargs):
        if current_user.id != 1:
            #return
            return abort(403)
        return f(*args, **kwargs)

    return wrapped_function

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ['app_key']
ckeditor = CKEditor(app)
Bootstrap4(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


##CONFIGURE TABLES
class RegisteredUsers(UserMixin,db.Model):
    __tablename__ = "registered_users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250),nullable=False)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    posts = relationship("BlogPost", back_populates="parent")
    comments = relationship("Comment", back_populates="parentRU")

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('registered_users.id'),nullable=False)
    parent = relationship("RegisteredUsers", back_populates="posts")     
    childrenCo = relationship("Comment", back_populates="parentBP") 
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

class Comment(db.Model):
    __tablename__="comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('registered_users.id'),nullable=False)
    parentRU = relationship("RegisteredUsers", back_populates="comments")
    blogPost_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'),nullable=False)
    parentBP = relationship("BlogPost", back_populates="childrenCo")


with app.app_context():
    db.create_all()

##LOGIN MANAGER
login_manager = LoginManager()
login_manager.init_app(app)

@app.route('/')
def get_all_posts():
    if current_user.is_authenticated:
        user_id = str(current_user.id)
    else:
        user_id = request.args.get('user_id')
    posts = db.session.query(BlogPost).all()    

    return render_template("index.html", all_posts=posts, user_id=user_id)
    #return redirect(url_for("get_all_posts",all_posts=posts))

@app.route('/register',methods=["GET","POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():        
        form_login=LoginForm()
        if RegisteredUsers.query.filter_by(email=form.email.data).first():
            
            flash('The email is already registered. Login instead.')    
            return render_template('login.html', form_login=form_login)       
     
        else: 
            password = form.password.data
            h_password = generate_password_hash(password, method='pbkdf2:sha256', 
                                                salt_length=8)        
            new_user = RegisteredUsers(
                name = form.name.data,
                email = form.email.data,
                password = h_password,
            )
            db.session.add(new_user)
            db.session.commit()
            # If you want to show the user Id use this line
            #return redirect(url_for("get_all_posts",user_id=new_user.id))
            return render_template('login.html', form_login=form_login )
        
    return render_template("register.html",form=form)   


@login_manager.user_loader
def load_user(user_id):
    return RegisteredUsers.query.get(user_id)

@app.route('/login',methods=['GET','POST'])
def login():
    form_login = LoginForm()
    if request.method == 'POST':      
        email = request.form.get('email')        
        user = RegisteredUsers.query.filter_by(email=email).first()
        if not(user):
            flash('The email does not exist in the database.')            
        elif check_password_hash(user.password, request.form.get('password')):
            login_user(user)           
            posts = db.session.query(BlogPost).all()
            return render_template("index.html", all_posts=posts,user_id=str(user.id))
            
        else:          
            flash(f'The password is incorrect!')

    return render_template("login.html",form_login=form_login)    

# @app.context_processor
# def inject_user_id():
#     return dict(global_user_id=current_user.id)

@app.route('/logout')
def logout():    
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>",methods=['GET','POST'])
def show_post(post_id):
    comment_form= CommentForm()
    if comment_form.validate_on_submit():
        new_comment = Comment(                
            text = comment_form.body.data,
            user_id = current_user.id,            
            blogPost_id = post_id,
            
        )
        db.session.add(new_comment)
        db.session.commit()
    requested_post = BlogPost.query.get(post_id)
    
    return render_template("post.html", post=requested_post, current_user_id=current_user.id,
                           comment_form=comment_form )

@app.route("/new-post",methods=['GET','POST'])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            user_id = current_user.id,#request.args.get('user_id'),
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            #author='current_user',#current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts",user_id = new_post.id))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>")
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    #app.run(host='0.0.0.0', port=5000)
    app.run(debug=True)

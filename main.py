import os
import re
import random
import hashlib
import hmac
from string import letters

import webapp2
import jinja2

from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir),
                               autoescape=True)

secret = 'secret'

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")


def valid_username(username):
    return username and USER_RE.match(username)

PASS_RE = re.compile(r"^.{3,20}$")


def valid_password(password):
    return password and PASS_RE.match(password)

EMAIL_RE = re.compile(r'^[\S]+@[\S]+\.[\S]+$')


def valid_email(email):
    return not email or EMAIL_RE.match(email)


def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)


def make_secure_val(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())


def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val


def make_salt(length=5):
    return ''.join(random.choice(letters) for x in xrange(length))


def make_pw_hash(name, pw, salt=None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '%s,%s' % (salt, h)


def users_key(group='default'):
    return db.Key.from_path('users', group)


def blog_key(name='default'):
    return db.Key.from_path('blogs', name)


def valid_pw(name, password, h):
    salt = h.split(',')[0]
    return h == make_pw_hash(name, password, salt)


class BlogHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        params['user'] = self.user
        return render_str(template, **params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header('Set-Cookie',
                                         '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))

    def render_post(response, posst):
        response.out.write('<b>' + post.subject + '</br><br>')
        response.out.write(post.content)


class HomePage(BlogHandler):
    def get(self):
        self.redirect('/blog')


class User(db.Model):
    name = db.StringProperty(required=True)
    pw_hash = db.StringProperty(required=True)
    email = db.StringProperty()

    @classmethod
    def by_id(cls, uid):
        return User.get_by_id(uid, parent=users_key())

    @classmethod
    def by_name(cls, name):
        u = User.all().filter('name =', name).get()
        return u

    @classmethod
    def register(cls, name, pw, email=None):
        pw_hash = make_pw_hash(name, pw)
        return User(parent=users_key(),
                    name=name,
                    pw_hash=pw_hash,
                    email=email)

    @classmethod
    def login(cls, name, pw):
        u = cls.by_name(name)
        if u and valid_pw(name, pw, u.pw_hash):
            return u


class Post(db.Model):
    subject = db.StringProperty()
    content = db.StringProperty()
    created = db.DateTimeProperty(auto_now_add=True)
    last_modified = db.DateTimeProperty(auto_now=True)
    username = db.StringProperty()

    def render(self):
        self._render_text = self.content.replace('\n', '</br>')
        comments = Comment.all().filter('post_id =', self.key().id())
        return render_str('post.html', p=self, comments=comments)


class Comment(db.Model):
    combody = db.StringProperty()
    created = db.DateTimeProperty(auto_now_add=True)
    last_modified = db.DateTimeProperty(auto_now=True)
    post_id = db.IntegerProperty()
    username = db.StringProperty()
    current_user = db.StringProperty()


class BlogMain(BlogHandler):
    def get(self):
        posts = greetings = Post.all().order('-created')
        self.render('blogmain.html', posts=posts)


class PostPage(BlogHandler):
    def get(self, post_id):
        key = db.Key.from_path('Post', int(post_id), parent=blog_key())
        post = db.get(key)

        if not post:
            self.error(404)
            return
        self.render('permalink.html', post=post)


class NewPost(BlogHandler):
    def get(self):
        if self.user:
            self.render('newpost.html')
        else:
            self.redirect('/login')

    def post(self):
        if not self.user:
            self.redirect('/blog')

        subject = self.request.get('subject')
        content = self.request.get('content')
        username = self.user.name

        if subject and content:
            p = Post(parent=blog_key(), subject=subject, content=content,
                     username=username)
            p.put()
            self.redirect('/blog/%s' % str(p.key().id()))
        else:
            error = "New posts must contain a subject and content!"
            self.render('newpost.html', subject=subject, content=content,
                        error=error)


class NewComment(BlogHandler):
    def get(self, post_id):
        if self.user:
            self.render('newcomment.html')
        else:
            self.redirect('/login')

    def post(self, post_id):
        if not self.user:
            self.redirect('/blog')

        combody = self.request.get('combody')

        key = db.Key.from_path('Post', int(post_id),
                               parent=blog_key())
        post = db.get(key)
        # uid = db.get_by_id(uid, parent=users_key())
        # user_id = self.user.user_id
        uid = self.read_secure_cookie('user_id')
        current_user = User.by_id(int(uid))
        username = self.user.name

        if not post:
            self.error(404)
            return
        if combody:
            c = Comment(parent=blog_key(),
                        combody=combody, post_id=int(post_id),
                        username=username, current_user=str(current_user))
            c.put()
            self.redirect('/blog/%s' % str(post_id))
        else:
            error = "New comments must contain a subject and content!"
            self.render('newcomment.html',
                        combody=combody,
                        error=error)


class CommentPage(BlogHandler):
    def get(self, comment_id):
        key = db.Key.from_path('Comment', int(comment_id), parent=blog_key())
        comment = db.get(key)

        if not comment:
            self.error(404)
            return
        self.render('commentpermalink.html', comment=comment)


class Signup(BlogHandler):
    def get(self):
        self.render("signup.html")

    def post(self):
        have_error = False
        self.username = self.request.get('username')
        self.password = self.request.get('password')
        self.verify = self.request.get('verify')
        self.email = self.request.get('email')

        params = dict(username=self.username, email=self.email)

        if not valid_username(self.username):
            params['error_username'] = "That is not a valid username"
            have_error = True

        if not valid_password(self.password):
            params['error_password'] = "That is not a valid password"
            have_errpr = True
        elif self.password != self.verify:
            params['error_verify'] = "Your passwords did not match"
            have_error = True

        if not valid_email(self.email):
            params['error_email'] = "That is not a valid Email"
            have_error = True

        if have_error:
            self.render('signup.html', **params)
        else:
            self.done()

        def done(self, *a, **kw):
            raise NotImplementedError


class Register(Signup):
    def done(self):
        u = User.by_name(self.username)
        if u:
            msg = 'That user already exists'
            self.render('signup.html', error_username=msg)
        else:
            u = User.register(self.username, self.password, self.email)
            u.put()

            self.login(u)
            self.redirect('/blog')


class Login(BlogHandler):
    def get(self):
        self.render('login.html')

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')

        u = User.login(username, password)
        if u:
            self.login(u)
            self.redirect('/blog')
        else:
            msg = 'Invalid Login'
            self.render('login.html', error=msg)


class LogOut(BlogHandler):
    def get(self):
        self.logout()
        self.redirect('/blog')


class Welcome(BlogHandler):
    def get(self):
        if self.user:
            self.render('welcome.html', username=self.user.name)
        else:
            self.redirect('/signup')

# class Edit(BlogHandler):
#     def get(self):
#         if self.user = user.name:

app = webapp2.WSGIApplication([('/', HomePage),
                              ('/welcome', Welcome),
                              ('/blog?', BlogMain),
                              ('/blog/([0-9]+)', PostPage),
                              ('/blog/newpost', NewPost),
                              ('/blog/([0-9]+)/comment', NewComment),
                              ('/signup', Register),
                              ('/login', Login),
                              ('/logout', LogOut),
                               ],
                              debug=True)

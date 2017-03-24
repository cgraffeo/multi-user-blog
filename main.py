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

USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")


def valid_username(username):
    return username and USER_RE.match(username)

PASS_RE = re.compile(r"^.{3,20}$")


def valid_password(password):
    return password and PASS_RE.match(password)

EMAIL_RE = re.compile(r'^[\S]+@[\S]+\.[\S]+$')


def valid_email(email):
    return not email or EMAIL_RE.match(email)


class BlogHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def blog_key(name='default'):
        return db.Key.from_path('blogs', name)

    def render_post(response, posst):
        response.out.write('<b>' + post.subject + '</br><br>')
        response.out.write(post.content)


class HomePage(BlogHandler):
    def get(self):
        self.render("homepage.html")


# Blog must include the following features:
# Front page that lists blog posts.
# A form to submit new entries.
# Blog posts have their own page.

class Post(db.Model):
    subject = db.StringProperty(required=True)
    content = db.TextProperty(required=True)
    created = db.DateTimeProperty(auto_add_now=True)
    last_modified = db.DateTimeProperty(auto_now=True)

    def render(self):
        self._render_text = self.content.replace('\n', '</br>')
        return render_str('post.html', p=self)


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

        if subject and content:
            p = Post(parent=blog_key(), subject=subject, content=content)
            p.put()
            self.redirect('/blog/%s' % str(p.key().id()))
        else:
            error = "New posts must contain a subject and content!"
            self.render('newpost.html', subject=subject, content=content,
                        error=error)


class Signup(BlogHandler):
    def get(self):
        self.render("signup.html")

    def post(self):
        have_error = False
        self.username = self.request.get('username')
        self.password = self.reqest.get('password')
        self.verify = self.request.get('verify')
        self.email = self.request.get('email')

        params = dict(username=self.username, email=self.email)

        if not valid_username(self.username):
            params['error_username'] = "That is not a valid username"
            have_error = True

        if not valid_password(self.password):
            params['error_password'] = "That is not a valid password"
        elif self.password != self.verify:
            params['error_verify'] = "Your passwords did not match"

        if not valid_email(self.email):
            params['error_email'] = "That is not a valid Email"

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


app = webapp2.WSGIApplication([('/', HomePage)
                               ],
                              debug=True)

import os
basedir = os.path.abspath(os.path.dirname(__file__))
from flask import render_template, flash, redirect, session, url_for, request, g, abort, jsonify
from werkzeug.utils import secure_filename

from flask.ext.login import login_user, logout_user, current_user, \
    login_required
from flask.ext.sqlalchemy import get_debug_queries
from datetime import datetime
from app import app, db, lm
from config import MAX_SEARCH_RESULTS, DATABASE_QUERY_TIMEOUT
from slugify import slugify

from .forms import SignupForm, LoginForm, EditForm, PostForm, SearchForm, CommentForm
from .models import User, Post, Comment
from .emails import follower_notification
from .utils import OAuthSignIn, pre_upload, GenericListView, ViewData, allowed_file
from PIL import Image
import json
from flask.views import MethodView


@app.route('/', methods=['GET'])
def index():
    return redirect(url_for('home'))

home_data = ViewData("home")
app.add_url_rule('/home/', view_func=GenericListView.as_view('home', home_data), methods=["GET", ])


class PostAPI(MethodView):
    decorators = [login_required]

    # Create a new Post
    def post(self, post_id=None):
        if post_id is None:     # Create a new post
            form = PostForm(request.form)
            if form.validate():
                result = {'iserror': False}
                slug = slugify(form.header.data)
                post = Post(body=form.post.data, timestamp=datetime.utcnow(),
                            author=g.user, photo=None, thumbnail=None, header=form.header.data,
                            writing_type=form.writing_type.data, slug=slug)
                db.session.add(post)
                db.session.commit()
                result['savedsuccess'] = True
                result['new_poem'] = render_template('comps/post.html', page_mark='detail', post=post, g=g)
                return json.dumps(result)
            form.errors['iserror'] = True
            return json.dumps(form.errors)
        else:   # Vote on post
            post_id = post_id
            user_id = g.user.id
            if not post_id:
                abort(404)
            post = Post.query.get_or_404(int(post_id))
            vote_status = post.vote(user_id=user_id)
            return jsonify(new_votes=post.votes, vote_status=vote_status)

    #  Read Post or Posts
    def get(self, page_mark=None, slug=None):
        if slug is None:    # Read all posts
            view_data = ViewData(page_mark)
            return render_template(view_data.template_name, **view_data.context)
        else:       # Read a single post
            detail_data = ViewData("detail", slug=slug)
            return render_template(detail_data.template_name, **detail_data.context)

    # Update Post
    def put(self):
        update_post = Post.query.get(request.form['post_id'])
        update_post.body = request.form['content']
        db.session.commit()
        result = {'updatedsuccess': True}
        return json.dumps(result)

    # Delete Post
    def delete(self, post_id):
        post = Post.query.get(post_id)
        db.session.delete(post)
        db.session.commit()
        result = {'deletedsuccess': True}
        return json.dumps(result)


# urls for Post API
post_api_view = PostAPI.as_view('posts')
# Create a new post
app.add_url_rule('/detail/', view_func=post_api_view, methods=["POST", ])
# Vote on post
app.add_url_rule('/vote/<int:post_id>', view_func=post_api_view, methods=["POST", ])
# Read a single post
app.add_url_rule('/detail/<slug>', view_func=post_api_view, methods=["GET", ])
# Read all posts for a specific view
app.add_url_rule('/<page_mark>/', view_func=post_api_view, methods=["GET", ])
# Update a single post
app.add_url_rule('/detail/', view_func=post_api_view, methods=["PUT", ])
# Delete a single post
app.add_url_rule('/detail/<int:post_id>', view_func=post_api_view, methods=["DELETE", ])


class UserAPI(MethodView):
    def post(self, user_name=None):
        if user_name is None:   # Create a new User
            form = SignupForm(request.form)
            if form.validate():
                result = {'iserror': False}
                newuser = User(form.firstname.data, form.email.data, firstname=form.firstname.data,
                               lastname=form.lastname.data,
                               password=form.password.data)
                db.session.add(newuser)
                db.session.add(newuser.follow(newuser))
                db.session.commit()
                remember_me = False
                if 'remember_me' in session:
                    remember_me = session['remember_me']
                    session.pop('remember_me', None)
                login_user(newuser, remember=remember_me)
                result['savedsuccess'] = True
                # result['new_profile'] = render_template('profile_user.html', profile_user=g.user)
                result['new_profile'] = g.user.nickname
                return json.dumps(result)
            form.errors['iserror'] = True
            return json.dumps(form.errors)
        else:   # Update User details
            form = EditForm()
            if request.is_xhr:  # First validate form using an async request
                form = EditForm()
                if form.validate(g.user):
                    result = {'iserror': False, 'savedsuccess': True}
                    return json.dumps(result)
                form.errors['iserror'] = True
                return json.dumps(form.errors)
            else:  # Once form is valid, original form is called and processed
                if form.validate(g.user):
                    profile_photo = request.files['profile_photo']
                    if profile_photo and allowed_file(profile_photo.filename):
                        filename = secure_filename(profile_photo.filename)
                        img_obj = dict(filename=filename, img=Image.open(profile_photo.stream), box=(128, 128),
                                       photo_type="thumb", crop=True,
                                       extension=form['profile_photo'].data.mimetype.split('/')[1].upper())
                        profile_photo_name = pre_upload(img_obj)
                        g.user.profile_photo = profile_photo_name
                    g.user.nickname = form.nickname.data
                    g.user.about_me = form.about_me.data
                    db.session.add(g.user)
                    db.session.commit()
                    return redirect("/profile/" + g.user.nickname)
                profile_data = ViewData("profile", nickname=g.user.nickname, form=form)
                return render_template(profile_data.template_name, **profile_data.context)

    # Read a single profile
    def get(self, nickname=None):
        if nickname is not None:
            profile_data = ViewData("profile", nickname=nickname)
            profile_data.form.nickname.data = g.user.nickname
            profile_data.form.about_me.data = g.user.about_me
            db.session.commit()
            return render_template(profile_data.template_name, **profile_data.context)
        else:
            if g.user is not None and g.user.is_authenticated():
                return redirect(url_for('home'))
            signup_data = ViewData("signup")
            return render_template(signup_data.template_name, **signup_data.context)

    # Delete User
    @login_required
    def delete(self, post_id):
        pass


# urls for User API
user_api_view = UserAPI.as_view('profile')
# Create a new user
app.add_url_rule('/profile/', view_func=user_api_view, methods=["POST", ])
# Update user
app.add_url_rule('/profile/<int:user_name>', view_func=user_api_view, methods=["POST", ])
# Read a single user
app.add_url_rule('/profile/<nickname>', view_func=user_api_view, methods=["GET", ])
# Read multiple users
app.add_url_rule('/profile/', view_func=user_api_view, methods=["GET", ])
# Delete a single user
app.add_url_rule('/profile/', view_func=user_api_view, methods=["DELETE"])


@app.route('/follow/<nickname>')    # Follow a User
@login_required
def follow(nickname):
    user = User.query.filter_by(nickname=nickname).first()
    if user is None:
        flash('User %s not found.' % nickname)
        return redirect(url_for('home'))
    if user == g.user:
        flash('You can\'t follow yourself!')
        return redirect(url_for('profile', nickname=nickname))
    u = g.user.follow(user)
    if u is None:
        flash('Cannot follow %s.' % nickname)
        return redirect(url_for('profile', nickname=nickname))
    db.session.add(u)
    db.session.commit()
    flash('You are now following %s.' % nickname)
    follower_notification(user, g.user)
    return redirect(url_for('profile', nickname=nickname))


@app.route('/unfollow/<nickname>')  # Unfollow a User
@login_required
def unfollow(nickname):
    user = User.query.filter_by(nickname=nickname).first()
    if user is None:
        flash('User %s not found.' % nickname)
        return redirect(url_for('home'))
    if user == g.user:
        flash('You can\'t unfollow yourself!')
        return redirect(url_for('profile', nickname=nickname))
    u = g.user.unfollow(user)
    if u is None:
        flash('Cannot unfollow %s.' % nickname)
        return redirect(url_for('profile', nickname=nickname))
    db.session.add(u)
    db.session.commit()
    flash('You have stopped following %s.' % nickname)
    return redirect(url_for('profile', nickname=nickname))


class AuthAPI(MethodView):
    def post(self):
        # Authorize data from manual login form
        form = LoginForm()
        if form.validate_on_submit():
            newuser = User.query.filter_by(email=form.email.data).first()
            remember_me = False
            if 'remember_me' in session:
                remember_me = session['remember_me']
                session.pop('remember_me', None)
            login_user(newuser, remember=remember_me)
            return redirect(url_for('profile'))
        else:
            return internal_error(form.errors[0])

    def get(self, get_provider=None, provider=None):
        # Internal request to get oauth provider info
        if get_provider is not None:
            if not current_user.is_anonymous():
                return redirect(url_for('home'))
            oauth = OAuthSignIn.get_provider(get_provider)
            return oauth.authorize()
        # Handles external provider oauth callback
        elif provider is not None:
            if not current_user.is_anonymous():
                return redirect(url_for('home'))
            oauth = OAuthSignIn.get_provider(provider)
            nickname, email = oauth.callback()
            if email is None:
                flash('Authentication failed.')
                return redirect(url_for('home'))
            currentuser = User.query.filter_by(email=email).first()
            if not currentuser:
                currentuser = User(nickname=nickname, email=email)
                db.session.add(currentuser)
                db.session.add(currentuser.follow(currentuser))
                db.session.commit()
            remember_me = False
            if 'remember_me' in session:
                remember_me = session['remember_me']
                session.pop('remember_me', None)
            login_user(currentuser, remember=remember_me)
            return redirect(request.args.get('next') or url_for('posts', page_mark='portfolio'))

        # Manual login form
        else:
            if g.user is not None and g.user.is_authenticated():
                return redirect(url_for('home'))
            login_data = ViewData("login")
            return render_template(login_data.template_name, **login_data.context)


# Urls for Auth API
auth_api_view = AuthAPI.as_view('login')
# Authenticate user
app.add_url_rule('/login/', view_func=auth_api_view, methods=["POST", ])
# Oauth login
app.add_url_rule('/login/<get_provider>', view_func=auth_api_view, methods=["GET", ])
# Oauth provider callback
app.add_url_rule('/callback/<provider>', view_func=auth_api_view, methods=["GET", ])
# Login form for returning user
app.add_url_rule('/login/', view_func=auth_api_view, methods=["GET", ])


class HelpersAPI(MethodView):
    decorators = [login_required]

    def post(self, post_id=None):
        if post_id is not None:     # Process Comment Form
            form = CommentForm()
            if form.validate_on_submit():
                result = {'iserror': False}
                comment = Comment(created_at=datetime.utcnow(), user_id=g.user.id, body=form.comment.data,
                                  post_id=post_id)
                db.session.add(comment)
                db.session.commit()
                result['savedsuccess'] = True
                result['new_comment'] = render_template('comps/detail/comment.html', comment=comment)
                return json.dumps(result)
            form.errors['iserror'] = True
            return json.dumps(form.errors)
        else:   # Process Search  Todo: Reimplement search
            if not g.search_form.validate_on_submit():
                return redirect(url_for('home'))
            return redirect(url_for('search_results', query=g.search_form.search.data))

    def get(self, query=None):
        if query is None:   # Logout
            logout_user()
            return redirect(url_for('login'))
        else:   # Search Results  Todo: Reimplement search
            results = Post.query.whoosh_search(query, MAX_SEARCH_RESULTS).all()
            upload_folder_name = app.config['UPLOAD_FOLDER_NAME']
            return render_template('search_results.html',
                                   query=query,
                                   results=results,
                                   upload_folder_name=upload_folder_name)


# Urls for Helpers API
helpers_api_view = HelpersAPI.as_view('helpers')
app.add_url_rule('/comment/<int:post_id>', view_func=helpers_api_view, methods=["POST", ])
app.add_url_rule('/logout', view_func=helpers_api_view, methods=["Get", ])
app.add_url_rule('/search', view_func=helpers_api_view, methods=["POST", ])


# Helper functions
@app.context_processor
def inject_static_url():
    local_static_url = app.static_url_path
    static_url = 'https://s3.amazonaws.com/netbardus/'
    if os.environ.get('HEROKU') is not None:
        local_static_url = static_url
    if not static_url.endswith('/'):
        static_url += '/'
    if not local_static_url.endswith('/'):
        local_static_url += '/'
    return dict(
        static_url=static_url,
        local_static_url=local_static_url
    )


@lm.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.before_request
def before_request():
    g.user = current_user
    if g.user.is_authenticated():
        g.user.last_seen = datetime.utcnow()
        db.session.add(g.user)
        db.session.commit()
        g.search_form = SearchForm()


@app.after_request
def after_request(response):
    for query in get_debug_queries():
        if query.duration >= DATABASE_QUERY_TIMEOUT:
            app.logger.warning(
                "SLOW QUERY: %s\nParameters: %s\nDuration: %fs\nContext: %s\n" %
                (query.statement, query.parameters, query.duration,
                 query.context))
    return response


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html', error=error), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html', error=error), 500

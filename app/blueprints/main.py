import random
from flask import (
    current_app,
    g,
    flash,
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    abort,
    make_response,
)
from ..models import Option, Page, User, Category, Tag, Post, Comment, Link
from ..forms import (
    LoginForm,
    PostForm,
    PageForm, 
    CategoryForm,
    TagForm,
    CommentForm,
    OptionForm,
    SearchForm,
    LoginCommentForm,
)
from ..extensions import db
from sqlalchemy import extract, and_, or_
from ..utils import redirect_back
from flask_login import current_user


main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    pagination = Post.query.order_by(Post.created.desc()).paginate(per_page=10)
    return render_template(
        "main/index.html", posts=pagination.items, pagination=pagination
    )


@main_bp.route("/page/<string:slug>")
def page(slug):
    page = Page.query.filter(Page.slug == slug).first_or_404()
    return render_template("main/page.html", page=page,)


@main_bp.route("/user/<int:user_id>")
def user(user_id):
    user = User.query.get_or_404(user_id)
    pagination = (
        Post.query.with_parent(user)
        .order_by(Post.created.desc())
        .paginate(per_page=10)
    )
    return render_template(
        "main/archive.html",
        type="作者",
        archive=user,
        posts=pagination.items,
        pagination=pagination,
    )

@main_bp.route("/category/<int:category_id>")
def category(category_id):
    category = Category.query.get_or_404(category_id)
    pagination = (
        Post.query.with_parent(category)
        .order_by(Post.created.desc())
        .paginate(per_page=10)
    )
    return render_template(
        "main/archive.html",
        type="分类",
        archive=category,
        posts=pagination.items,
        pagination=pagination,
    )


@main_bp.route("/tag/<int:tag_id>")
def tag(tag_id):
    tag = Tag.query.get_or_404(tag_id)
    pagination = (
        Post.query.with_parent(tag).order_by(Post.created.desc()).paginate(per_page=10)
    )
    return render_template(
        "main/archive.html",
        type="标签",
        archive=tag,
        posts=pagination.items,
        pagination=pagination,
    )


@main_bp.route("/archive/<int:archive_year>/<int:archive_month>")
def archive(archive_year, archive_month):

    posts = Post.query.filter(
        and_(
            extract("year", Post.created) == archive_year,
            extract("month", Post.created) == archive_month,
        )
    )
    pagination = posts.paginate(per_page=10)
    archive = {
        "name": str(archive_year) + "年" + str(archive_month) + "月",
        "posts": posts.all(),
    }
    return render_template(
        "main/archive.html",
        type="归档",
        archive=archive,
        posts=pagination.items,
        pagination=pagination,
    )


@main_bp.route("/search")
def search():
    keyword = request.args.get("keyword")
    pagination = Post.query.filter(
        or_(
            Post.content.like("%" + keyword + "%"), Post.title.like("%" + keyword + "%")
        )
    ).paginate(per_page=10)
    archive = {"name": keyword, "posts": pagination.items}
    return render_template(
        "main/archive.html",
        type="搜索",
        archive=archive,
        posts=archive["posts"],
        pagination=pagination,
    )


@main_bp.route("/post/<int:post_id>")
def post(post_id):

    if current_user.is_authenticated:
        form = LoginCommentForm()
    else:
        form = CommentForm()

    # 一篇文章
    post = Post.query.get_or_404(post_id)
    # 递增阅读次数
    post.read_count = post.read_count + 1
    db.session.commit()
    # 评论列表
    pagination = (
        Comment.query.with_parent(post)
        .filter_by(reviewed=True)
        .order_by(Comment.created.desc())
        .paginate(per_page=10)
    )

    # 获取上篇下篇
    p_index = -1
    n_index = -1
    posts = Post.query.order_by(Post.created)
    for i, p in enumerate(posts):
        if p.id == post_id:
            p_index = i - 1
            n_index = i + 1

    if n_index == posts.count():
        next_post = None
    else:
        next_post = posts[n_index]

    if p_index == -1:
        prev_post = None
    else:
        prev_post = posts[p_index]

    return render_template(
        "main/post.html",
        post=post,
        post_comments=pagination.items,
        pagination=pagination,
        form=form,
        prev_post=prev_post,
        next_post=next_post,
    )


@main_bp.route("/post/random")
def random_post():
    post = Post.query
    if not post.count():
        flash('没有找到文章','info')
        return redirect(url_for("main.index"))
    i = random.randint(0, post.count() - 1)
    return redirect(url_for("main.post", post_id=post[i].id))


@main_bp.route("/post/<int:post_id>/comment", methods=["POST"])
def comment_post(post_id):  # 评论帖子或回复帖子中的评论

    form = CommentForm()

    if form.validate_on_submit():

        comment = Comment(
            post_id=post_id,
            author=form.author.data,
            mail=form.mail.data,
            url=form.url.data,
            content=form.content.data,
            ip=request.remote_addr,
        )

        # 管理员发表的评论 或 评论审核被关闭
        if current_user.is_authenticated or not int(g.options["comment_review"]):
            comment.reviewed = True

        # 被回复的评论id
        comment_id = request.args.get("comment_id")
        if comment_id:  # 关联父评论
            comment.replied = Comment.query.get_or_404(comment_id)

            # send_new_reply_email(replied_comment)

        db.session.add(comment)
        db.session.commit()

        if int(comment.reviewed):
            flash("发表成功", "success")
        else:
            flash("发表成功, 请等待审核", "success")

        response = make_response()
        # response.mimetype = "text/html; charset=utf-8"
        response.location = url_for("main.post", post_id=post_id)
        response.status_code = 302
        if not current_user.is_authenticated:
            response.set_cookie("remember_author", form.author.data)
            response.set_cookie("remember_mail", form.mail.data)
            response.set_cookie("remember_url", form.url.data)
        return response


@main_bp.route("/comment/<int:comment_id>/reply", methods=["GET", "POST"])
def reply_comment(comment_id):

    comment = Comment.query.get_or_404(comment_id)

    return redirect(
        url_for(
            ".post",
            post_id=comment.post_id,
            comment_id=comment_id,
            author=comment.author,
        )
        + "#comment-form"
    )

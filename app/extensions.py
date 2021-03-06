from flask_sqlalchemy import SQLAlchemy
from flask_debugtoolbar import DebugToolbarExtension
from flask_bootstrap import Bootstrap
from flask_login import LoginManager, current_user
from flask_wtf import CSRFProtect
from flask_moment import Moment

db = SQLAlchemy()
toolbar = DebugToolbarExtension()
bootstrap = Bootstrap()
login_manager = LoginManager()
csrf = CSRFProtect()
moment = Moment()

@login_manager.user_loader
def load_user(user_id):
    from .models import User

    user = User.query.get(int(user_id))
    return user

login_manager.login_view = "auth.login"
login_manager.login_message = "请先登录"
login_manager.login_message_category = "warning"

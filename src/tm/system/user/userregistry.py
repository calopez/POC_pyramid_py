"""Default user object generator."""
# Standard Library
from datetime import timedelta
import typing as t

# Pyramid
from zope.interface import implementer

# SQLAlchemy
from sqlalchemy import func

from tm.utils.time import now
from tm.system.user.interfaces import IUserRegistry
from tm.system.user.models import User

@implementer(IUserRegistry)
class UserRegistry:
    """Default user backend which uses SQLAlchemy to store User models.

    Provides default user actions
    """

    def __init__(self, request):
        """Initialize UserRegistry.

        :param request:Pyramid request.
        """
        self.dbsession = request.dbsession
        self.registry = request.registry

    @property
    def User(self):
        """Currently configured User SQLAlchemy model.

        :return: Class User.
        """
        from tm.system.user.models import User
        return User

    @property
    def Group(self):
        """Currently configured Group SQLAlchemy model.

        :return: Class Group.
        """
        from tm.system.user.models import Group
        return Group

    @property
    def Activation(self):
        """Currently configured Activation SQLAlchemy model.

        :return: Class Activation.
        """
        from tm.system.user.models import Activation
        return Activation

    @property
    def AuthorizationCode(self):
        """Currently configured AuthorizationCode SQLAlchemy model.

        :return: Class AuthorizationCode.
        """
        from tm.system.user.models import AuthorizationCode
        return AuthorizationCode

    def all(self):
        return self.dbsession.query(self.User).all()

    def set_password(self, user, password):
        """Hash a password for persistent storage.

        :param user: User object.
        :param password: User password.
        """
        from .password import Argon2Hasher
        hasher = Argon2Hasher()
        hashed = hasher.hash_password(password)
        user.hashed_password = hashed

    def verify_password(self, user, password) -> bool:
        """Validate user password.

        :param user: User object.
        :param password: User password.
        :return: Boolean of the password verification.
        """
        if not user.hashed_password:
            # User password not set, always fail
            return False

        from .password import Argon2Hasher
        hasher = Argon2Hasher()
        return hasher.verify_password(user.hashed_password, password)

    def get_by_username(self, username):
        """Return the User with the given username.

        We always compare the lowercase version of User.username and username.

        :param username: Username to be used.
        :return: User object.
        """
        username = username.lower()
        user_class = self.User
        return self.dbsession.query(user_class).filter(func.lower(user_class.username) == username).first()

    def get_by_email(self, email):
        """Return the User with the given email.

        We always compare the lowercase version of User.email and email.

        :param email: Email to be used.
        :return: User object.
        """
        email = email.lower()
        user_class = self.User
        return self.dbsession.query(user_class).filter(func.lower(user_class.email) == email).first()

    def get_by_activation(self, activation):
        """Return the User with the given activation.

        :param activation: Activation object..
        :return: User object.
        """
        user_class = self.User
        return self.dbsession.query(user_class).filter(user_class.activation_id == activation.id).first()

    def can_login(self, user):
        """Verify if user is allowed do login.

        :param user: User object.
        :return: Boolean
        """
        return user.can_login()

    def get_groups(self, user):
        """Groups for a user.

        :param user: User object.
        :return: List of groups for this user.
        """
        return user.groups

    def create_authorization_code(self, user: User, login_source: str = None):
        """Sets authorization code for user.

        :param user: User
        :return: [User, authorization_code, authorization_code_expiry_seconds]. ``None`` if user is not allowed to login
        """

        if not user.can_login():
            return None

        authorization_code_expiry_seconds = int(self.registry.settings.get("tm.oauth.authorization_code_expiry_seconds", 30))

        auth_code = self.AuthorizationCode()
        auth_code.expires_at = now() + timedelta(seconds=authorization_code_expiry_seconds)
        self.dbsession.add(auth_code)
        self.dbsession.flush()
        user.authorization_code = auth_code

        assert user.authorization_code.code, "Could not generate the authorization code"

        return user, auth_code.code, authorization_code_expiry_seconds



    def create_password_reset_token(self, email):
        """Sets password reset token for user.

        :param email: Email to be used.
        :return: [User, password reset token, token expiration in seconds]. ``None`` if user is disabled or is not email login based.
        """
        user = self.get_by_email(email)
        assert user, "Got password reset request for non-existing email".format(email)

        if not self.can_login(user):
            return None

        activation_token_expiry_seconds = int(self.registry.settings.get("tm.registry.activation_token_expiry_seconds", 24 * 3600))

        activation = self.Activation()
        activation.expires_at = now() + timedelta(seconds=activation_token_expiry_seconds)
        self.dbsession.add(activation)
        self.dbsession.flush()
        user.activation = activation

        assert user.activation.code, "Could not generate the password reset code"

        return user, activation.code, activation_token_expiry_seconds

    def create_email_activation_token(self, user):
        """Create activation token for the user to be used in the email

        :param user: User object.
        :return: Tuple (email activation code, expiration in seconds)
        """
        activation = self.Activation()
        activation_token_expiry_seconds = int(self.registry.settings.get("tm.registry.activation_token_expiry_seconds", 24 * 3600))
        activation.expires_at = now() + timedelta(seconds=activation_token_expiry_seconds)

        self.dbsession.add(activation)
        self.dbsession.flush()
        user.activation = activation
        return activation.code, activation_token_expiry_seconds

    def get_authenticated_user_by_username(self, username, password):
        """Authenticate incoming user using username and password.

        :param username: Provided username.
        :param password: Provided password.
        :return: User instance of none if password does not match
        """
        user = self.get_by_username(username)
        if user and self.verify_password(user, password):
            return user
        return None

    def get_authenticated_user_by_email(self, email, password):
        """Authenticate incoming user using email and password.

        :param email: Provided email.
        :param password: Provided password.
        :return: User instance of none if password does not match
        """
        user = self.get_by_email(email)
        if user and self.verify_password(user, password):
            return user
        return None

    def get_user_by_id(self, id):
        """Resolve the authenticated user by a session token reference.

        :param id: user id
        :return: User object.
        """
        return self.dbsession.query(self.User).get(id)

    def get_user_by_password_reset_token(self, token):
        """Get user by a password token issued earlier.

        Consume any activation token.

        :param token: Reset password token to be used to return the user.
        :return: User instance of none if token is not found.
        """
        activation = self.dbsession.query(self.Activation).filter(self.Activation.code == token).first()

        if activation:
            if activation.is_expired():
                return None
            user = self.get_by_activation(activation)
            return user
        return None

    def validate_authorization_code(self, client_id, authorization_code):
        """Validate authorization code and get user

        * Consume any authorization code. This is one time operation once got it must be deleted
        * Must validate the code belongs to the client_id parameter

        :param client_id: User id
        :param authorization_code: Authorization code
        :return: User instance or none if code is not found.
        """
        result = self.dbsession.query(self.User, self.AuthorizationCode). \
                                   filter(self.User.authorization_code_id == self.AuthorizationCode.id).\
                                   filter(self.User.id == client_id).\
                                   filter(self.AuthorizationCode.code == authorization_code).one_or_none()
        user = None
        if result:
            user, auth_code = result
            if auth_code.is_expired():
                user = None
            self.dbsession.delete(auth_code) # consume the auth code

        return user

    def activate_user_by_email_token(self, token):
        """Get user by a password token issued earlier.

        Consume any activation token.

        :param token: Password token to be used to return the user.
        :return: User instance of none if token is not found.
        """
        activation = self.dbsession.query(self.Activation).filter(self.Activation.code == token).first()

        if activation:
            if activation.is_expired():
                return None

            user = self.get_by_activation(activation)
            user.activated_at = now()
            self.dbsession.delete(activation)
            return user

        return None

    def reset_password(self, user, password):
        """Reset user password and clear all pending activation issues.

        :param user: User object,
        :param password: New password.
        """
        self.set_password(user, password)

        if not user.activated_at:
            user.activated_at = now()
        self.dbsession.delete(user.activation)

    def sign_up(self, registration_source, user_data):
        """Sign up a new user with credentials

        :param registration_source: Indication where the user came from.
        :param user_data: Payload with new user information.
        :return: Newly created User object.
        """
        password = user_data.pop("password", None)

        u = self.User(**user_data)

        if password:
            self.set_password(u, password)

        self.dbsession.add(u)
        self.dbsession.flush()

        # Generate default username (should not be exposed by default)
        u.username = u.generate_username()

        # Record how we created this record
        u.registration_source = registration_source

        self.dbsession.flush()
        return u

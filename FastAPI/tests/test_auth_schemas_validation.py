import pytest
from pydantic import ValidationError

from app.schemas.auth import ChangePasswordRequest, UserProfileUpdate, UserRegister


def test_user_register_password_min_and_match_validators():
    with pytest.raises(ValidationError):
        UserRegister(email="u@example.com", password="short", confirm_password="short")
    with pytest.raises(ValidationError):
        UserRegister(email="u@example.com", password="longenough1", confirm_password="different1")


def test_change_password_validators():
    with pytest.raises(ValidationError):
        ChangePasswordRequest(new_password="short", confirm_password="short")
    with pytest.raises(ValidationError):
        ChangePasswordRequest(new_password="longenough1", confirm_password="different1")


def test_user_profile_update_password_change_validators():
    with pytest.raises(ValidationError):
        UserProfileUpdate(new_password="newpassword1", confirm_new_password="newpassword1")
    with pytest.raises(ValidationError):
        UserProfileUpdate(current_password="oldpassword", new_password="newpassword1", confirm_new_password="different1")

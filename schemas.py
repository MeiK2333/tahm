from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import get_db, User as UserModel
from settings import SECRET_KEY

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(BaseModel):
    id: int
    username: str
    email: str
    nickname: Optional[str] = None
    # 是否可以查看数据文件
    readable: Optional[bool] = None
    # 是否可以写（创建、修改）数据文件
    writeable: Optional[bool] = None
    # 是否可以管理（看其他用户，给权限等）
    admin: Optional[bool] = None

    class Config:
        orm_mode = True


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms="HS256")
        user_id: int = payload.get("id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


permission_exception = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="HTTP_403_FORBIDDEN",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user_r(user: User = Depends(get_current_user)):
    """ 获取用户同时判断权限，权限以 wra 区分（writeable、readable、admin） """
    if not user.readable:
        raise permission_exception
    return user


async def get_current_user_w(user: User = Depends(get_current_user)):
    """ 获取用户同时判断权限，权限以 wra 区分（writeable、readable、admin） """
    if not user.writeable:
        raise permission_exception
    return user


async def get_current_user_a(user: User = Depends(get_current_user)):
    """ 获取用户同时判断权限，权限以 wra 区分（writeable、readable、admin） """
    if not user.admin:
        raise permission_exception
    return user


def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None, db: Session = None
):
    to_encode = {"id": data.get("id")}
    user_id: int = to_encode.get("id")
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if user is None:
        # 因为此处的数据是从 GitHub 获取而非用户提交，因此可以信任，直接创建入库
        db_user = UserModel(
            id=user_id,
            username=data.get("login"),
            email=data.get("email"),
            nickname=data.get("name"),
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return encoded_jwt

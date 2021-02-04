from typing import List

import aiohttp
import uvicorn
from fastapi import FastAPI, Depends, HTTPException
from fastapi import responses
from sqlalchemy.orm import Session
from pathlib import Path
from models import Base, engine, get_db, User as UserModel
from schemas import (
    User,
    get_current_user,
    create_access_token,
    get_current_user_a,
    get_current_user_r,
)
from settings import CLIENT_ID, CLIENT_SECRET, DATA_DIR

Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/users", response_model=List[User])
async def all_users(
    current_user: User = Depends(get_current_user_a), db: Session = Depends(get_db)
):
    users = []
    for user in db.query(UserModel).filter():
        if user.id == current_user.id:
            pass
        users.append(user)
    return users


@app.get("/problems", response_model=List[int])
def get_problems(current_user: User = Depends(get_current_user_r)):
    problem_path = Path(DATA_DIR)
    problems = []
    for file in problem_path.iterdir():
        if file.is_dir():
            try:
                problems.append(int(file.name))
            except Exception as ex:
                print(repr(ex))
    problems.sort()
    return problems


@app.get("/problems/{pid}", response_model=List[str])
def get_problem(pid: int, current_user: User = Depends(get_current_user_r)):
    problem_path = Path(DATA_DIR).joinpath(str(pid))
    files = []
    for file in problem_path.iterdir():
        if file.is_file():
            files.append(file.name)
    files.sort()
    return files


@app.get("/token")
async def login(code: str = None, db: Session = Depends(get_db)):
    if not code:
        return responses.RedirectResponse(
            f"https://github.com/login/oauth/authorize?client_id={CLIENT_ID}",
            status_code=302,
        )
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://github.com/login/oauth/access_token",
            json={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": code},
            headers={"accept": "application/json"},
        ) as resp:
            body = await resp.json()
            access_token = body["access_token"]
        async with session.get(
            "https://api.github.com/user",
            headers={
                "accept": "application/json",
                "Authorization": f"token {access_token}",
            },
        ) as resp:
            user_dict = await resp.json()
    if not user_dict:
        raise HTTPException(status_code=400, detail="")
    access_token = create_access_token(user_dict, db=db)
    return {"access_token": access_token, "token_type": "bearer"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

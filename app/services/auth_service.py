from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthCredentials
import jwt
from dotenv import load_dotenv
import logging
import os

load_dotenv()

# JWT Secret Key
JWT_SECRET = os.getenv("JWT_SECRET")
security = HTTPBearer()

async def token_required(credentials: HTTPAuthCredentials = Depends(security)):
    token = credentials.credentials
    
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"verify_sub": False})
        current_user_id = data['user_id']
    except Exception as e:
        logging.error(f"Error decoding token: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token is invalid!"
        )
    
    return {"user_id": current_user_id, "token": token}


app = FastAPI()

# Usage in a route
@app.get("/protected")
async def protected_route(auth_data: dict = Depends(token_required)):
    user_id = auth_data["user_id"]
    token = auth_data["token"]
    return {"message": f"Hello user {user_id}"}
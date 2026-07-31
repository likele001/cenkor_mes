"""创建平台管理员：python scripts/init_platform_admin.py [username] [password]"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SessionLocal
from app.crud.platform_user import create_platform_user, get_platform_user_by_username


def main():
    username = sys.argv[1] if len(sys.argv) > 1 else "platform"
    password = sys.argv[2] if len(sys.argv) > 2 else "platform123"
    db = SessionLocal()
    try:
        if get_platform_user_by_username(db, username):
            print(f"平台用户已存在: {username}")
            return
        create_platform_user(db, username, password, full_name="平台管理员")
        db.commit()
        print(f"已创建平台管理员: {username}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

"""نقطة تشغيل العامل من مجلد backend: python worker.py"""

from app.worker import main

if __name__ == "__main__":
    raise SystemExit(main())

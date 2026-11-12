# تشغيل العامل على Fly.io أو VPS

الهدف: عملية دائمة تسحب مهام `graph_build` و`report_generate` من طابور Neon.
الملفات المطلوبة موجودة في المستودع: `Dockerfile.worker` و`fly.worker.toml`
و`deploy/istishraf-worker.service`.

---

## أ) Fly.io (أسرع طريق، بلا إدارة خادم)

```bash
# مرة واحدة
curl -L https://fly.io/install.sh | sh
fly auth login

# في جذر المستودع
fly launch --no-deploy --copy-config --name istishraf-worker -c fly.worker.toml

# الأسرار (نفس قيم Vercel)
fly secrets set -c fly.worker.toml \
  DATABASE_URL="postgresql://…neon.tech/neondb?sslmode=require" \
  LLM_API_KEY="…" \
  LLM_BASE_URL="https://api.groq.com/openai/v1" \
  LLM_MODEL_NAME="openai/gpt-oss-120b" \
  SECRET_KEY="$(openssl rand -hex 32)"

fly deploy -c fly.worker.toml
fly logs -c fly.worker.toml          # يجب أن ترى: «العامل … بدأ العمل»
```

- لا منفذ HTTP ولا نطاق: العامل يسحب فقط.
- التكلفة: جهاز `shared-cpu-1x/1GB` يعمل دائمًا، بضع دولارات شهريًا.
- بعد التشغيل: `curl /health | jq .queue` يُظهر `persistent_workers: 1`
  و`queued_mode: true`، ويتحول بناء الشبكة إلى `202`.

---

## ب) VPS (أي مزوّد، Ubuntu 22.04+)

```bash
sudo apt update && sudo apt install -y python3.12 python3.12-venv
sudo useradd -m -s /bin/bash istishraf
sudo git clone https://github.com/paradisesoap653-dotcom/istishraf-future.git /opt/istishraf
sudo chown -R istishraf:istishraf /opt/istishraf

sudo -u istishraf python3.12 -m venv /opt/istishraf/.venv
sudo -u istishraf /opt/istishraf/.venv/bin/pip install -r /opt/istishraf/backend/requirements-worker.txt
```

`/etc/istishraf-worker.env` (صلاحيات 600، ملكية root):

```ini
DATABASE_URL=postgresql://…neon.tech/neondb?sslmode=require
LLM_API_KEY=…
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL_NAME=openai/gpt-oss-120b
ISTISHRAF_JOB_LEASE_SECONDS=900
```

```bash
sudo cp /opt/istishraf/deploy/istishraf-worker.service /etc/systemd/system/
sudo chmod 600 /etc/istishraf-worker.env
sudo systemctl daemon-reload
sudo systemctl enable --now istishraf-worker
sudo journalctl -u istishraf-worker -f     # «العامل … بدأ العمل»
```

تحديث لاحق: `sudo -u istishraf git -C /opt/istishraf pull && sudo systemctl restart istishraf-worker`.

---

## ج) Docker على أي خادم

```bash
docker build -f Dockerfile.worker -t istishraf-worker .
docker run -d --restart=unless-stopped --name istishraf-worker \
  -e DATABASE_URL=… -e LLM_API_KEY=… -e LLM_BASE_URL=… -e LLM_MODEL_NAME=… \
  -v istishraf_uploads:/app/backend/uploads \
  istishraf-worker
docker logs -f istishraf-worker
```

---

## التحقق بعد التشغيل

```bash
curl -s https://istishraf-future.vercel.app/health | jq .queue
# { "workers_alive": 1, "persistent_workers": 1, "queued_mode": true, "pending": 0, … }
```

ثم جرّب بناء شبكة من الموقع: يجب أن يعيد `202` وتظهر المهمة في
`SELECT id, kind, status, attempts FROM jobs ORDER BY id DESC LIMIT 5;`
وتنتقل `pending → running → succeeded`.

## إيقاف العامل
يرسل SIGTERM فيُكمل المهمة الجارية ثم يخرج؛ وإن قُتل عنوةً تنتهي مدة التأجير
فتُعاد المهمة إلى الطابور تلقائيًا.

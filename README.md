# Azure + AWS Multi-Cloud DR — URL Shortener

Varsayılan bellek içi depoda veriler süreç yeniden başladığında kaybolur ve süreçler arasında paylaşılmaz.

## Yerel çalıştırma

Python 3.12 ile:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest -q
```

Ortam değişkenleri: `CLOUD_ROLE` (`azure` veya `aws`, varsayılan `azure`), `WRITER_MODE` (`active`, `standby` veya `frozen`, varsayılan `active`) ve `WRITER_EPOCH` (negatif olmayan tam sayı, varsayılan `1`). AWS üzerinde normal koşullarda `WRITER_MODE=standby` açıkça ayarlanmalıdır. `frozen` yanıtındaki `Retry-After` değeri 60 saniyedir.

`/health/dr` yalnızca yerel yapılandırmayı gösterir. Health kontrolleri yazma yetkisi vermez; writer mode dağıtık fencing sağlamaz. DNS failover ve write promotion ayrı işlemlerdir ve bu aşamada uygulanmamıştır. Readiness uygulamanın çalıştığını gösterir; Cosmos DB veya diğer bulut bağımlılıklarını kontrol etmez.

## Cosmos DB

`REPOSITORY_BACKEND` varsayılan olarak `memory`, Cosmos için `cosmos` seçilir. Cosmos seçildiğinde `COSMOS_ENDPOINT`, `COSMOS_DATABASE` ve `COSMOS_CONTAINER` zorunludur. Kimlik doğrulama Azure Identity `DefaultAzureCredential` kullanır; uygun Azure kimliği ve Cosmos DB veri erişim izinleri gereklidir. Uygulama kaynak oluşturmaz.

Küçük ölçekli PoC için container partition key'i `/id` olarak seçilmiştir; okumalar ID ve partition key ile yapılır. Cosmos kaynakları sonraki görevde oluşturulacaktır. Bu adapter gerçek Cosmos DB ortamında henüz test edilmemiştir.

## Docker

```bash
docker build -t url-shortener .
docker run --rm -p 8000:8000 -e WRITER_MODE=active url-shortener
```

## Örnek istekler

```bash
curl -X POST http://localhost:8000/api/urls -H 'Content-Type: application/json' -d '{"original_url":"https://example.com/path"}'
curl http://localhost:8000/api/urls/KOD
curl -i http://localhost:8000/KOD
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/dr
```

`KOD` yerine oluşturma yanıtındaki `id` değerini kullanın. Canlı bulut doğrulaması, replikasyon ve failback henüz uygulanmamıştır; RPO veya RTO garantisi verilmez.

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

Küçük ölçekli PoC için container partition key'i `/id` olarak seçilmiştir; okumalar ID ve partition key ile yapılır. Sweden Central'daki gerçek Cosmos DB hesabına yerel FastAPI üzerinden bağlantı, kayıt oluşturma, okuma ve yönlendirme testi başarıyla yapılmıştır. Ayrıntılar [altyapı dokümantasyonunda](infra/README.md) yer alır.

## DynamoDB

`REPOSITORY_BACKEND=dynamodb`, `AWS_REGION=eu-west-1` ve `DYNAMODB_TABLE` ile seçilir; tablo önceden mevcut olmalıdır. Kimlik bilgileri boto3 standart credential zincirinden alınır. AWS secondary için `CLOUD_ROLE=aws` ve `WRITER_MODE=standby` açıkça ayarlanmalıdır; varsayılan writer modu active olduğu için bunları deployment sırasında doğrulayın. Standby yalnızca API üzerinden yazmayı engeller, dağıtık fencing sağlamaz.

Tablonun partition key alanı `id` (String), sort key yoktur. Bu alan Cosmos `/id` partition key ve kayıt kimliği ile eşleşir. Diğer alanlar URL, UTC zamanları, origin cloud, writer epoch, version ve deleted değerleridir. Çakışmada koşullu `PutItem` mevcut kaydı değiştirmez; `GetItem` tutarlı point-read kullanır. Okuma için tabloya kapsamlı `dynamodb:GetItem`, yalnızca yazma yetkisi verilen kimlikler için ayrıca `dynamodb:PutItem` gerekir. Normal standby çalışma rolünü salt okunur tutun; promotion ayrı IAM yetkisi ve açık onay gerektirir. `mcdr-dev-urls` tablosu ve salt okunur Lambda execution rolü oluşturuldu.

## AWS Lambda secondary hazırlığı

FastAPI için `app.lambda_handler.handler` Mangum giriş noktası ve [Lambda Terraform modülü](infra/modules/aws-lambda-api/README.md) hazırlandı. Önceki apply sırasında Lambda, execution role ve log grubu oluşturuldu; reserved concurrency ayarı kota nedeniyle başarısız oldu. Lambda AWS'de mevcut; doğrudan invoke ile health uçları 200, DynamoDB'de bulunmayan kayıt 404 ve standby POST 403 döndürdü. API Gateway veya function URL oluşturulmadı. Uygulama AWS secondary olarak standby başlar. `AWS_REGION`, Lambda runtime tarafından sağlanan ayrılmış değişkendir; elle ayarlanmaz. Gelecekte API Gateway HTTP API, erişim ve yetkilendirme tasarımı ile ayrı plan ve onaydan sonra eklenmelidir.

## Docker

```bash
docker build -t url-shortener .
docker run --rm -p 8000:8000 -e WRITER_MODE=active url-shortener
```

## GHCR image yayını

Manuel yayın workflow'u `.github/workflows/publish-image.yml` ile ilk image yayımlandı ve anonim pull doğrulandı. Sonraki yayınlar için ayrı açık onayla GitHub'da **Actions → Publish container image → Run workflow** üzerinden gözden geçirilmiş dal seçilmelidir. Workflow Python 3.12 testleri başarılıysa `linux/amd64` image'ını `ghcr.io/frkndmr7/azure-aws-multi-cloud-dr:<tam-commit-SHA>` etiketiyle yayımlar. `GITHUB_TOKEN` için `contents: read` ve `packages: write` kullanır; PAT gerekmez. Repository Actions ayarları ile mevcut paket varsa onun Actions erişimi yayın öncesinde doğrulanmalıdır.

Başarılı çalışmanın özetinde kaynak commit ve `ghcr.io/frkndmr7/azure-aws-multi-cloud-dr@sha256:<digest>` görüntülenir. Container Apps için etiketi değil bu digest referansını `CONTAINER_APP_IMAGE` olarak kullanın. SHA etiketi de yeniden yazılabilir; digest yayımlanan içeriği sabitler. Bağımlılıklar ve temel image sürümleri aralıklarla belirtildiği için aynı commit'in yeniden build edilmesi aynı digest'i garanti etmez.

Paket görünürlüğünü public varsaymayın: İlk yayın sonrası GitHub profilinde **Packages → azure-aws-multi-cloud-dr → Package settings** bölümünde görünürlüğü ve **Manage Actions access** izinlerini kontrol edin. Public yapılması gerekiyorsa bunun herkese açık erişim sağlayacağını değerlendirip ayrı açık onay alın; sonra yetkili kişi **Change visibility** adımını kullanabilir. Mevcut paket izinleri veya devralınan repository izinleri bu işlemi etkileyebilir. Public image anonim indirilebilir; yayın öncesinde image içeriğini ve `.dockerignore` kapsamını inceleyin. Bu workflow Azure deployment veya provider kaydı yapmaz.

## Örnek istekler

```bash
curl -X POST http://localhost:8000/api/urls -H 'Content-Type: application/json' -d '{"original_url":"https://example.com/path"}'
curl http://localhost:8000/api/urls/KOD
curl -i http://localhost:8000/KOD
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/dr
```

`KOD` yerine oluşturma yanıtındaki `id` değerini kullanın. Azure Container App Cosmos backend ile frozen ve ingress kapalı çalışıyor; Managed Identity ile point-read doğrulandı. AWS'de DynamoDB tablosu ve Lambda oluşturuldu; Doğrudan Lambda health ve salt okunur DynamoDB testleri başarılı oldu. API Gateway, replikasyon ve failback henüz uygulanmadı. RPO veya RTO garantisi verilmez.

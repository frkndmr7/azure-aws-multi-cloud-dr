# AWS Lambda secondary hazırlığı

Önceki apply sırasında Python 3.12 x86_64 Lambda, execution role, inline IAM policy ve 7 gün retention'lı CloudWatch log grubu oluşturuldu; reserved concurrency ayarı kota nedeniyle başarısız oldu. Lambda AWS'de mevcut; doğrudan invoke ile health uçları 200, DynamoDB'de bulunmayan kayıt 404 ve standby POST 403 döndürdü. API Gateway, function URL, Lambda resource policy veya başka public endpoint oluşturulmaz. IAM role yalnızca mevcut tablonun `dynamodb:GetItem` ve bu log grubunun stream'lerine `logs:CreateLogStream` / `logs:PutLogEvents` izinlerini verir; `PutItem` izni yoktur. `standby` API yazmasını reddeder ancak dağıtık fencing değildir. Lambda invoke yetkisi olan mevcut IAM kimlikleri yine de fonksiyonu çağırabilir; hesap politikaları incelenmelidir.

Lambda 256 MB ve 15 saniye timeout kullanır. Reserved concurrency tanımlanmaz; bu, eşzamanlı çağrı sayısını 1 ile sınırlamaz ve fonksiyon hesap genelindeki ayrılmamış kapasiteyi kullanır. Bölge `eu-west-1` olarak provider'da seçilir; `AWS_REGION` ayrılmış değişkenini Lambda runtime sağlar, Terraform bunu ayarlamaz. Tablo adı ve ARN bağımsız DynamoDB Terragrunt state çıktılarından okunur; bu modül tabloyu yönetmez. State hassas olabilir, Git'e eklemeyin.

## ZIP hazırlama

ZIP, public image registry veya ek container registry gerektirmeyen basit bir PoC dağıtımıdır. Yerel Python/pip ve ağ erişimiyle şu komut Python 3.12 Linux x86_64 wheel'lerini indirir ve uygulama kaynaklarıyla geçici ZIP üretir:

```bash
sh scripts/build_lambda_zip.sh /tmp/mcdr-secondary-lambda.zip
export LAMBDA_ZIP_PATH=/tmp/mcdr-secondary-lambda.zip
cd infra/live/aws/dev/lambda-api
terragrunt validate
terragrunt plan
```

ZIP'i Git'e eklemeyin. Bağımlılıklar aralıklarla tanımlandığı için farklı zamanlarda yapılan build'lerin aynı içeriği üretmesi garanti değildir; gözden geçirilmiş ZIP ve hash'i apply öncesi koruyun. Yerel çapraz platform paketleme Lambda runtime testinin yerini tutmaz. Mevcut paket AWS Python 3.12 runtime üzerinde doğrudan invoke ile doğrulandı; sonraki her ZIP ayrıca test edilmelidir.

Gelecekte API Gateway HTTP API entegrasyonu, route ve stage ile ayrıca tasarlanacaktır. Varsayılan execute-api endpoint'i ve `$default` stage public erişime yol açabileceğinden stage/invoke izinleri ve erişim kontrolü birlikte incelenmeden açılmamalıdır. Bu aşama için mevcut planda API Gateway yoktur. Kaynakları oluşturmadan önce güncel plan, IAM policy, maliyet ve hesap ayrı açık onayla değerlendirilmelidir.

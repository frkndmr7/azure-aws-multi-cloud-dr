# Azure Cosmos DB altyapısı

`modules/azure-cosmos` kaynak tanımlarını, `live/azure/dev/cosmos` ise dev ortamı girdilerini içerir. Henüz deployment yapılmamıştır.

## Hazırlık ve doğrulama

Terraform 1.5+ (2.0'dan küçük), Terragrunt ve Azure CLI gerekir. Kontroller Terraform 1.14.3, Terragrunt 1.1.6 ve AzureRM 4.81.0 ile yapılmıştır. Azure erişimi gerektiren sonraki işlemlerden önce:

```bash
az login
az account set --subscription '<subscription-id>'
export ARM_SUBSCRIPTION_ID='<subscription-id>'
export COSMOS_ACCOUNT_NAME='<globally-unique-account-name>'
cd infra/live/azure/dev/cosmos
terragrunt init
terragrunt validate
terragrunt plan
```

Hesap adı 3–44 küçük harf, rakam veya tire içermeli ve küresel olarak benzersiz olmalıdır. `COSMOS_ACCOUNT_NAME` verilmezse plan doğrulaması başarısız olur. Veritabanı, container, bölge ve maliyet ayarları `terragrunt.hcl` girdilerinden değiştirilebilir. Plan Azure kimliği ve subscription gerektirir; kod doğrulaması Azure kaynağı oluşturmaz. Planı ve olası maliyeti inceleyip açık onay aldıktan sonra ayrı bir adımda `terragrunt apply` kullanılabilir. Terraform bağımlılıkları sırayla resource group, Cosmos account, SQL database ve `/id` partition key'li SQL container oluşturur. Kaynaklarda `prevent_destroy` vardır; bu koruma kaynak bloğu kaldırılırsa geçerli değildir.

## Kapasite, güvenlik ve state

Varsayılan hesap tek bölgelidir; container için 400 RU/s provisioned throughput ve Free Tier seçimi kullanılır. Serverless etkin değildir. Free Tier subscription uygunluğuna bağlıdır, hesap oluşturulurken seçilir ve garanti edilmez; uygulanmazsa provisioned throughput kullanım olmasa da ücretlendirilir. Sınır aşımı, depolama, varsayılan periyodik yedekleme, ağ ve başka hizmetler de ücret doğurabilir. Azure fiyatlarını ve Free Tier uygunluğunu deployment öncesinde kontrol edin. Zone redundancy ve çok bölgeli yazma etkin değildir.

Terraform endpoint, database ve container adlarını output olarak verir; uygulamada bunlar sırasıyla `COSMOS_ENDPOINT`, `COSMOS_DATABASE` ve `COSMOS_CONTAINER`, ayrıca `REPOSITORY_BACKEND=cosmos` olarak ayarlanır. Account key output edilmez. Cosmos DB data-plane RBAC yetkileri, ileride uygulamanın managed identity'sine ayrıca verilmelidir; Azure yönetim izinleri tek başına bu erişimi sağlamaz. Container Apps veya identity henüz oluşturulmamıştır. Hesap için varsayılan public network erişimi ve Azure'ın varsayılan yedekleme davranışı kullanılır; ağ erişimini ve yetkilendirmeyi deployment öncesi değerlendirin.

State, `live/azure/dev/cosmos/terraform.tfstate` konumunda yereldir; `.gitignore` ile dışlanır ve account key dahil hassas bilgiler içerebilir. Güvenli saklayın, paylaşmayın ve Git'e eklemeyin. Yerel state ekip çalışması veya CI/CD için uygun değildir; ileride güvenli, kilitlemeli bir remote backend gerekir. `terragrunt init` ve `validate` gerçek Cosmos DB bağlantısını doğrulamaz.

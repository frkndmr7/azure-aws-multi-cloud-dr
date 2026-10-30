# AWS DynamoDB PoC

Bu modül `eu-west-1` bölgesindeki `mcdr-dev-urls` tablosunu yönetir; tablo oluşturulmuş ve `ACTIVE` durumu doğrulanmıştır. AWS provider `6.24.0` sabitlenmiştir ve hesap ID kontrolü yanlış hesapta işlem yapılmasını engeller. Ayrı yerel Terragrunt state dosyası hassas olabilir; Git'e eklenmemeli ve güvenli saklanmalıdır.

- Tek partition key `id` (String); sort key ve secondary index yok. Cosmos `/id` ile uyumludur.
- `PAY_PER_REQUEST` kapasite tahsisi gerektirmez; istek, depolama ve diğer kullanım ücretleri oluşabilir. Sıfır maliyet garanti değildir.
- Point-in-time recovery başlangıçta kapalıdır: sürekli yedekleme maliyeti oluşmaz, ancak yanlışlıkla silinen veya değiştirilen veriler bu yöntemle geri alınamaz. Canlı veri öncesi yeniden değerlendirilmelidir.
- DynamoDB deletion protection ve Terraform `prevent_destroy` açıktır. Terraform koruması kaynak bloğu kaldırıldığında geçerli değildir; bu önlemler yedekleme yerine geçmez.
- TTL tanımlı değildir: kayıtlar otomatik silinmez. Streams kapalıdır: replikasyon/failback akışı henüz yoktur; daha sonra ayrıca tasarlanmalıdır.
- AWS varsayılan şifrelemesi kullanılır. Tabloya erişim için uygulama IAM rolü ve diğer kaynaklar bu modülde oluşturulmaz.

Gelecekteki değişikliklerde plan ve olası maliyetler incelendikten sonra apply için ayrıca açık onay gereklidir. `terraform validate` veya plan tek başına bir değişikliğin uygulandığı anlamına gelmez.

# CLAUDE.md

**Önce `PROJECT_SPEC.md` dosyasını oku.** Bu projenin tek doğru kaynağıdır. Spec'te olmayan özellik ekleme.

## Dil
- Kullanıcıyla **Türkçe** konuş.
- Kod, değişken/dosya adları, commit mesajları, README ve `docs/` **İngilizce**.

## Çalışma kuralları (PROJECT_SPEC.md Bölüm 0)
1. **Faz faz ilerle.** Aynı anda tek faz (Bölüm 9). Faz sonunda testleri çalıştır, sonucu ≤10 satırda raporla, kullanıcının "continue" demesini bekle.
2. **Token tasarrufu (katı).**
   - Küçük değişiklikte dosyayı baştan yazma; hedefli edit kullan.
   - Az önce yazdığın dosyaları tekrar okuma; büyük dosyaları geri yapıştırma.
   - Açıklamalar kısa; kod ve test düzyazıdan önemli.
   - Geliştirme/testlerde **mock provider** ve kayıtlı fixture kullan. Gerçek LLM yalnızca `@pytest.mark.live` testlerinde (`RUN_LIVE=1` yoksa atlanır).
3. **Güvenlik ve ayrıştırma kodunda önce test yaz** (redaction, sanitizer, diff parser, chunker). Önce başarısız test, sonra kod.
4. **Küçük commit'ler**, Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`). **Yalnızca kullanıcı isteyince commit at.**
5. **Önce sor:** yeni runtime bağımlılığı, genel config şeması değişikliği, güvenlik kuralı değişikliği, spec'te olmayan her şey.
6. **Faz "bitti" tanımı:** `check` hedefi geçer (lint + tip + test + güvenlik taraması), dokümanlar güncel, Bölüm 9 kabul kriterleri sağlanmış.

## Ortam
- Windows 11 + Git Bash (MINGW64); `make` yok. Görev çalıştırıcı: **`just`** (`justfile`; spec'teki Makefile hedefleriyle aynı). Spec'te "make check" geçen yerde `just check` kullan.
- `just`, venv içinde (`rust-just` dev bağımlılığı): `.venv/Scripts/just check` veya venv aktifken `just check`.
- Kurulum: `python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"` (veya `just setup`).

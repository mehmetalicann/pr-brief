import pytest

from pr_brief.security.redact import redact

# Split so that secret scanners do not flag this file; the test values are fake.
PK_BEGIN = "-----BEGIN " + "PRIVATE KEY-----"
PK_END = "-----END " + "PRIVATE KEY-----"

# Fake secrets are assembled at runtime so that scanners do not flag this file.
CASES = [
    ("AKIA" + "IOSFODNN7EXAMPLE", "AWS key"),
    ("ghp_" + "a" * 36, "GitHub token"),
    ("github_pat_" + "A1b2C3d4E5f6G7h8I9j0K1", "GitHub fine-grained token"),
    ("glpat-" + "x1Y2z3A4b5C6d7E8f9G0", "GitLab token"),
    ("sk-" + "A1b2C3d4" * 6, "OpenAI-style key"),
    ("sk-ant-" + "api03-" + "Zy9Xw8Vu7Ts6Rq5Po4Nm3", "Anthropic-style key"),
    ("AIza" + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q", "Google API key"),
    ("xoxb-" + "1234567890-abcdefghijkl", "Slack token"),
    ("sk_live_" + "A1b2C3d4E5f6G7h8", "Stripe key"),
    ("eyJhbGciOiJIUzI1NiJ9" + ".eyJzdWIiOiIxMjM0In0.abc123def456", "JWT"),
    ("-----BEGIN RSA " + "PRIVATE KEY-----\nMIIE...\n-----END RSA " + "PRIVATE KEY-----", "key"),
    ("pass" + 'word = "hunter2hunter2"', "assignment"),
    ('"api_key": "' + "abcd1234efgh5678" + '"', "json assignment"),
    ("TOKEN" + "=abc123def456ghi789", "env assignment"),
    ("AccountKey=" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0U1v2W3x4Y5z6==", "Azure key"),
    ("Authorization: Bearer " + "abcdef0123456789abcdef", "bearer token"),
    ("https://deploy:" + "s3cretPass99" + "@git.example.org/repo.git", "URL credentials"),
    ("contact: jane.doe@example.com", "email"),
    ("db at 10.12.0.5 and 192.168.1.20 and 172.16.4.4", "private IPv4"),
    ("blob aB3dE5fG7hJ9kL1mN2pQ4rS6tU8vW0xY done", "high entropy"),
]


@pytest.mark.parametrize(("raw", "label"), CASES)
def test_secrets_are_masked(raw: str, label: str) -> None:
    out = redact(f"+ line {raw} end")
    assert raw not in out.text, label
    assert "[REDACTED" in out.text, label
    assert out.count >= 1, label


@pytest.mark.parametrize(("raw", "label"), CASES)
def test_redaction_is_idempotent(raw: str, label: str) -> None:
    once = redact(f"+ line {raw} end").text
    assert redact(once).text == once, label


@pytest.mark.parametrize(("raw", "label"), CASES)
def test_line_count_is_preserved(raw: str, label: str) -> None:
    text = f"@@ -1,2 +1,2 @@\n+ line {raw} end\n+next"
    assert redact(text).text.count("\n") == text.count("\n"), label


def test_normal_code_untouched() -> None:
    code = "+ def add(a: int, b: int) -> int:\n+     return a + b"
    out = redact(code)
    assert out.text == code
    assert out.count == 0


@pytest.mark.parametrize(
    "line",
    [
        "+ token = get_token_value()",
        "+ max_tokens = 900",
        '+ password = os.environ["PW"]',
        "+ secret_key = settings.SECRET",
        "+ api-key: ${{ secrets.LLM_API_KEY }}",
        '+ password: "${{ secrets.DB_PASSWORD }}"',
        "+ sha = da39a3ee5e6b4b0d3255bfef95601890afd80709",
        "+ class ThisIsAVeryLongButPlainCamelCaseIdentifierName:",
        "+ path = src/pr_brief/core/prompts_and_chunker_helpers.py",
        "+ ip = 8.8.8.8 and 172.32.0.1 and 11.0.0.1",
        "+ decorator @dataclass and user@localhost",
        '+ "tokens": "Tokens: input {input} · output {output}",',  # prose label, not a secret
        '+ password_hint = "your first pet name"',
    ],
)
def test_common_code_is_not_a_false_positive(line: str) -> None:
    assert redact(line).text == line


def test_masks_value_only_and_keeps_the_key_for_assignments() -> None:
    out = redact("+ pass" + 'word = "hunter2hunter2"').text
    assert out.startswith('+ password = "[REDACTED:')
    assert "hunter2hunter2" not in out


def test_private_key_block_keeps_diff_prefixes_and_surrounding_lines() -> None:
    text = (
        "@@ -0,0 +1,5 @@\n"
        "+" + PK_BEGIN + "\n"
        "+MIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n"
        "+abcdefghijklmnop\n"
        "+" + PK_END + "\n"
        "+after = 1"
    )
    out = redact(text).text.split("\n")
    assert len(out) == 6
    assert all(line.startswith("+") for line in out[1:])
    assert out[-1] == "+after = 1"
    assert "MIIEvQ" not in "\n".join(out)
    assert "abcdefghijklmnop" not in "\n".join(out)


def test_removed_private_key_lines_are_masked_too() -> None:
    text = PK_BEGIN + "\n-MIIEvQIBADANBgkqhkiG9w0\n-" + PK_END + "\n keep"
    out = redact(text).text
    assert "MIIEvQ" not in out
    assert out.endswith("\n keep")


def test_unterminated_private_key_stops_at_the_next_hunk() -> None:
    text = "+" + PK_BEGIN + "\n+MIIEvQIBADANBgkqhkiG9w0\n@@ -9 +9 @@\n+x = 1"
    out = redact(text).text
    assert "MIIEvQ" not in out
    assert out.endswith("@@ -9 +9 @@\n+x = 1")


def test_secrets_in_removed_and_context_lines_are_masked_as_well() -> None:
    token = "ghp_" + "b" * 36
    out = redact(f"-old = {token}\n ctx = {token}\n+new = 1").text
    assert token not in out


def test_result_reports_counts_per_kind() -> None:
    token = "ghp_" + "c" * 36
    out = redact(f"{token} {token} contact a.b@example.com")
    assert out.kinds["github-token"] == 2
    assert out.kinds["email"] == 1
    assert out.count == 3


def test_empty_and_whitespace_input() -> None:
    assert redact("").text == ""
    assert redact("\n\n").count == 0


def test_single_line_json_private_key_is_masked() -> None:
    # A JSON string: the newlines are the two characters backslash + n, not real line breaks.
    line = '{"private_key": "' + PK_BEGIN + "\\nMIIEvQ\\n" + PK_END + '\\n"}'
    assert "\n" not in line
    out = redact(line)
    assert "MIIEvQ" not in out.text
    assert out.text.endswith('\\n"}')
    assert out.kinds["private-key"] == 1

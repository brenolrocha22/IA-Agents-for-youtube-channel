"""Provedores de narração. `sapi` usa as vozes do Windows (local, sem custo); `silent` gera silêncio temporizado."""
from __future__ import annotations

import base64
import re
import subprocess
import sys
import wave
from pathlib import Path

from ..config import env

SAMPLE_RATE = 22050
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_VOICE_RE = re.compile(r"^[A-Za-z0-9 ._-]{1,60}$")


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def write_silence(path: Path, seconds: float) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x00\x00" * int(seconds * SAMPLE_RATE))


def concat_wavs(parts: list[Path], out: Path, gap_s: float) -> list[tuple[float, float]]:
    """Concatena WAVs mono 16-bit com pausa entre eles; devolve (início, duração) de cada parte."""
    spans, t = [], 0.0
    gap = b"\x00\x00" * int(gap_s * SAMPLE_RATE)
    with wave.open(str(out), "wb") as dst:
        dst.setnchannels(1)
        dst.setsampwidth(2)
        dst.setframerate(SAMPLE_RATE)
        for i, p in enumerate(parts):
            with wave.open(str(p), "rb") as src:
                if (src.getnchannels(), src.getsampwidth(), src.getframerate()) != (1, 2, SAMPLE_RATE):
                    raise ValueError(f"Formato WAV inesperado em {p.name}")
                frames = src.readframes(src.getnframes())
            dur = len(frames) / 2 / SAMPLE_RATE
            spans.append((t, dur))
            dst.writeframes(frames)
            t += dur
            if i < len(parts) - 1:
                dst.writeframes(gap)
                t += gap_s
    return spans


def speech_span(path: Path, win_s: float = 0.02, rel: float = 0.05) -> tuple[float, float]:
    """Início e fim da fala medidos pela energia do áudio."""
    import array

    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        a = array.array("h", w.readframes(w.getnframes()))
    win = max(1, int(sr * win_s))
    env = [max(abs(x) for x in a[i:i + win]) for i in range(0, max(1, len(a) - win), win)]
    th = max(env) * rel if env else 0
    on = [i * win_s for i, e in enumerate(env) if e > th]
    return (on[0], on[-1] + win_s) if on else (0.0, len(a) / sr)


# As vozes SAPI informam AudioPosition na taxa nativa (16 kHz), mesmo gravando em 22,05 kHz.
SAPI_POSITION_SCALE = 16000 / SAMPLE_RATE


def calibrate(words: list[dict], wav: Path, scale: float = SAPI_POSITION_SCALE) -> list[dict]:
    """Converte as marcas do sintetizador para o tempo real do arquivo e confere com a energia do áudio."""
    start, end = speech_span(wav)
    scaled = [{**w, "t": round(w["t"] * scale, 3)} for w in words]
    if abs(scaled[0]["t"] - start) <= 0.25 and scaled[-1]["t"] < end:
        return scaled
    # Segurança: mapeia linearmente o intervalo reportado para o intervalo de fala medido.
    t0, t1 = words[0]["t"], words[-1]["t"] or 1.0
    span_end = end - 0.6 * (end - start) / max(1, len(words))
    return [{**w, "t": round(start + (w["t"] - t0) / max(1e-6, t1 - t0) * (span_end - start), 3)} for w in words]


class SilentTTS:
    name = "silent"
    license = "Silêncio gerado localmente (sem narração)"

    def is_available(self) -> bool:
        return True

    timestamps = "estimados (sem narração)"

    def synthesize_many(self, items: list[tuple[str, Path]], lang: str, rate: int = 0) -> list[list[dict]]:
        out_marks = []
        for text, out in items:
            words = text.split()
            dur = max(1.0, len(words) / 2.6)
            write_silence(out, dur)
            out_marks.append([{"t": dur * i / len(words), "word": w} for i, w in enumerate(words)])
        return out_marks


class SapiTTS:
    name = "sapi"
    license = "Voz sintética Microsoft SAPI do Windows — termos de uso comercial a verificar pelo proprietário"

    def voice(self, lang: str) -> str:
        v = env("TTS_VOICE_PT", "Microsoft Maria Desktop") if lang == "pt" else env("TTS_VOICE_EN", "Microsoft Zira Desktop")
        if not _VOICE_RE.match(v):
            raise ValueError("Nome de voz inválido")
        return v

    def is_available(self) -> bool:
        return sys.platform == "win32"

    timestamps = "do sintetizador (evento SpeakProgress por palavra)"

    def synthesize_many(self, items: list[tuple[str, Path]], lang: str, rate: int = 0) -> list[list[dict]]:
        """Um processo PowerShell para todos os trechos. Texto lido de arquivo (sem injeção).

        Retorna, por trecho, o instante real de cada palavra no áudio gerado (SpeakProgress.AudioPosition).
        """
        q = lambda p: "'" + str(p).replace("'", "''") + "'"  # noqa: E731
        texts, outs, marks = [], [], []
        for text, out in items:
            txt = out.with_suffix(".txt")
            txt.write_text(text, encoding="utf-8")
            texts.append(q(txt))
            outs.append(q(out))
            marks.append(q(out.with_suffix(".marks.tsv")))
        script = "\n".join([
            "$ErrorActionPreference='Stop'",
            "Add-Type -AssemblyName System.Speech",
            "$code = @'",
            "using System; using System.IO; using System.Collections.Generic; using System.Speech.Synthesis;",
            "using System.Speech.AudioFormat;",
            "public static class CiosTts {",
            "  public static void Run(string voice, int rate, string[] texts, string[] outs, string[] marks) {",
            "    using (var s = new SpeechSynthesizer()) {",
            "      s.SelectVoice(voice); s.Rate = rate;",
            f"      var fmt = new SpeechAudioFormatInfo({SAMPLE_RATE}, AudioBitsPerSample.Sixteen, AudioChannel.Mono);",
            "      for (int i = 0; i < texts.Length; i++) {",
            "        var lines = new List<string>();",
            "        EventHandler<SpeakProgressEventArgs> h = (o, e) => lines.Add(",
            "          e.AudioPosition.TotalMilliseconds.ToString(System.Globalization.CultureInfo.InvariantCulture) + \"\\t\" + e.Text);",
            "        s.SpeakProgress += h;",
            "        s.SetOutputToWaveFile(outs[i], fmt);",
            "        s.Speak(File.ReadAllText(texts[i], System.Text.Encoding.UTF8));",
            "        s.SetOutputToNull();",
            "        s.SpeakProgress -= h;",
            "        File.WriteAllLines(marks[i], lines, System.Text.Encoding.UTF8);",
            "      }",
            "    }",
            "  }",
            "}",
            "'@",
            "Add-Type -TypeDefinition $code -ReferencedAssemblies System.Speech",
            f"[CiosTts]::Run({q(self.voice(lang))}, {int(max(-5, min(5, rate)))}, @({','.join(texts)}), @({','.join(outs)}), @({','.join(marks)}))",
        ])
        encoded = base64.b64encode(script.encode("utf-16-le")).decode()
        proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                              capture_output=True, text=True, timeout=90 + 20 * len(items), creationflags=_NO_WINDOW)
        result = []
        for _, out in items:
            out.with_suffix(".txt").unlink(missing_ok=True)
            mf = out.with_suffix(".marks.tsv")
            words = []
            if mf.exists():
                for line in mf.read_text(encoding="utf-8-sig").splitlines():
                    ms, _, word = line.partition("\t")
                    if word.strip():
                        words.append({"t": float(ms) / 1000, "word": word.strip()})
                mf.unlink()
            result.append(calibrate(words, out) if words and out.exists() else words)
        if proc.returncode != 0:
            raise RuntimeError(f"SAPI falhou: {proc.stderr[-500:]}")
        return result


class WinRTTTS:
    """Vozes modernas do Windows (OneCore), ex.: 'Microsoft Daniel' (pt-BR, masculina). Local e gratuita.

    Tom e ritmo via SSML (voz mais grave e séria). Marcas de tempo por palavra vêm do próprio sintetizador
    (IncludeWordBoundaryMetadata) e são conferidas com a energia do áudio.
    """

    name = "winrt"
    license = "Voz sintética Microsoft (Windows OneCore) — termos de uso comercial a verificar pelo proprietário"
    timestamps = "do sintetizador (metadados de palavra do Windows)"

    def voice(self) -> str:
        v = env("TTS_VOICE_PT_WINRT", "Microsoft Maria")  # feminina por padrão (pedido do proprietário)
        if not _VOICE_RE.match(v):
            raise ValueError("Nome de voz inválido")
        return v

    def is_available(self) -> bool:
        return sys.platform == "win32"

    def synthesize_many(self, items: list[tuple[str, Path]], lang: str, rate: int = 0) -> list[list[dict]]:
        q = lambda p: "'" + str(p).replace("'", "''") + "'"  # noqa: E731
        pitch = env("TTS_PITCH", "-12%" if "Daniel" in self.voice() else "+0%")
        speed = env("TTS_RATE", {0: "-5%", 1: "-2%"}.get(rate, "+8%") if rate >= 0 else "-5%")  # fala mais mansa
        if not re.fullmatch(r"[+-]?\d{1,2}%", pitch) or not re.fullmatch(r"[+-]?\d{1,2}%", speed):
            raise ValueError("TTS_PITCH/TTS_RATE inválidos (ex.: -12%)")
        lines = [
            "$ErrorActionPreference='Stop'",
            "Add-Type -AssemblyName System.Runtime.WindowsRuntime",
            "$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and "
            "$_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]",
            "function Await($op, [Type]$t) { $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op)); "
            "$task.Wait(-1) | Out-Null; $task.Result }",
            "$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]",
            "$null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]",
            "$s = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer",
            f"$s.Voice = ([Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object {{ $_.DisplayName -eq {q(self.voice())} }})[0]",
            "if (-not $s.Voice) { throw 'Voz não instalada' }",
            "$s.Options.IncludeWordBoundaryMetadata = $true",
        ]
        raw_paths = []
        for text, out in items:
            txt, raw, marks = out.with_suffix(".txt"), out.with_suffix(".raw.wav"), out.with_suffix(".marks.tsv")
            txt.write_text(text, encoding="utf-8")
            raw_paths.append(raw)
            lines += [
                f"$t = [Security.SecurityElement]::Escape([IO.File]::ReadAllText({q(txt)}, [Text.Encoding]::UTF8).Trim())",
                "$ssml = \"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='pt-BR'>"
                f"<prosody pitch='{pitch}' rate='{speed}'>$t</prosody></speak>\"",
                "$st = Await ($s.SynthesizeSsmlToStreamAsync($ssml)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])",
                "$n = [uint32]$st.Size; $r = New-Object Windows.Storage.Streams.DataReader($st.GetInputStreamAt(0))",
                "$null = Await ($r.LoadAsync($n)) ([uint32]); $b = New-Object byte[] $n; $r.ReadBytes($b)",
                f"[IO.File]::WriteAllBytes({q(raw)}, $b)",
                "$m = foreach ($tr in $st.TimedMetadataTracks) { foreach ($c in $tr.Cues) { "
                "$c.StartTime.TotalMilliseconds.ToString([Globalization.CultureInfo]::InvariantCulture) + \"`t\" + $c.Text } }",
                f"[IO.File]::WriteAllLines({q(marks)}, [string[]]$m, [Text.Encoding]::UTF8)",
            ]
        encoded = base64.b64encode("\n".join(lines).encode("utf-16-le")).decode()
        proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                              capture_output=True, text=True, timeout=90 + 20 * len(items), creationflags=_NO_WINDOW)
        if proc.returncode != 0:
            raise RuntimeError(f"Voz do Windows falhou: {proc.stderr[-500:]}")
        from . import ffmpeg  # converte para o formato comum do pipeline (22,05 kHz mono 16 bits)

        result = []
        for (_, out), raw in zip(items, raw_paths):
            ffmpeg.run(["-y", "-i", str(raw), "-ac", "1", "-ar", str(SAMPLE_RATE), "-sample_fmt", "s16", str(out)], 120)
            raw.unlink(missing_ok=True)
            out.with_suffix(".txt").unlink(missing_ok=True)
            mf = out.with_suffix(".marks.tsv")
            words = []
            for line in mf.read_text(encoding="utf-8-sig").splitlines() if mf.exists() else []:
                ms, _, word = line.partition("\t")
                if word.strip():
                    words.append({"t": float(ms) / 1000, "word": word.strip()})
            mf.unlink(missing_ok=True)
            result.append(calibrate(words, out, scale=1.0) if words else words)
        return result


class SpeechifyTTS:
    """Speechify (API oficial, paga). Desativado sem SPEECHIFY_API_KEY e SPEECHIFY_VOICE_ID.

    O ID da voz é escolhido pelo proprietário na conta Speechify (ex.: voz feminina carioca). A API devolve o áudio e
    as marcas de tempo por palavra. Não usa o gerador do site (automatizá-lo violaria os termos).
    """

    name = "speechify"
    license = "Voz Speechify via API — uso comercial conforme o plano contratado (verificar termos)"
    timestamps = "do provedor (speech marks da API Speechify)"
    API = "https://api.sws.speechify.com/v1/audio/speech"

    def is_available(self) -> bool:
        return bool(env("SPEECHIFY_API_KEY") and env("SPEECHIFY_VOICE_ID"))

    def synthesize_many(self, items: list[tuple[str, Path]], lang: str, rate: int = 0) -> list[list[dict]]:
        import httpx

        from . import ffmpeg

        result = []
        for text, out in items:
            r = httpx.post(self.API, timeout=120, headers={"Authorization": f"Bearer {env('SPEECHIFY_API_KEY')}"},
                           json={"input": text, "voice_id": env("SPEECHIFY_VOICE_ID"), "audio_format": "wav",
                                 "language": "pt-BR", "model": env("SPEECHIFY_MODEL", "simba-multilingual")})
            if r.status_code >= 400:  # nunca inclui a chave na mensagem
                raise RuntimeError(f"Speechify respondeu {r.status_code}: {r.text[:300]}")
            data = r.json()
            raw = out.with_suffix(".raw.wav")
            raw.write_bytes(base64.b64decode(data["audio_data"]))
            ffmpeg.run(["-y", "-i", str(raw), "-ac", "1", "-ar", str(SAMPLE_RATE), "-sample_fmt", "s16", str(out)], 120)
            raw.unlink(missing_ok=True)
            marks = (data.get("speech_marks") or {}).get("chunks") or []
            words = [{"t": float(m.get("start_time", 0)) / 1000, "word": str(m.get("value", "")).strip()} for m in marks
                     if str(m.get("value", "")).strip()]
            if not words:  # sem marcas: estima pela energia do áudio (aviso no log do job)
                start, end = speech_span(out)
                toks = text.split()
                words = [{"t": start + (end - start) * i / max(1, len(toks)), "word": w} for i, w in enumerate(toks)]
            result.append(calibrate(words, out, scale=1.0))
        return result


def get_tts():
    # Speechify entra automaticamente quando configurado; senão a voz do Windows.
    wanted = env("TTS_PROVIDER", "speechify" if SpeechifyTTS().is_available() else "winrt")
    for provider in (SpeechifyTTS(), WinRTTTS(), SapiTTS()):
        if wanted == provider.name and provider.is_available():
            return provider
    return SilentTTS()

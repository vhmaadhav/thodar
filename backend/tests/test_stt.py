import pytest

from thodar.ai.stt import ElevenLabsSTT, IndicConformerSTT, OffshoreNotAllowed, SarvamSTT, get_stt
from thodar.config import Settings


def test_default_is_sarvam_in_india():
    stt = get_stt(Settings(_env_file=None))
    assert isinstance(stt, SarvamSTT) and stt.processes_in.startswith("India")


def test_indicconformer_is_self_hosted():
    stt = get_stt(Settings(_env_file=None, stt_provider="indicconformer"))
    assert isinstance(stt, IndicConformerSTT) and "own server" in stt.processes_in


def test_offshore_provider_is_refused_unless_opted_in():
    with pytest.raises(OffshoreNotAllowed):
        get_stt(Settings(_env_file=None, stt_provider="elevenlabs"))
    stt = get_stt(Settings(_env_file=None, stt_provider="elevenlabs", allow_offshore_processing=True))
    assert isinstance(stt, ElevenLabsSTT)


def test_eval_error_rates():
    from scripts.eval_stt import error_rates
    assert error_rates("சனிக்கிழமை வரேன்", "சனிக்கிழமை வரேன்") == (0.0, 0.0)
    wer, _ = error_rates("நாளை வரேன்", "நாளை வரமாட்டேன்")
    assert wer == 0.5

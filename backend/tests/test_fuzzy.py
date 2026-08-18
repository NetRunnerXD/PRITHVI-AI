"""Fuzzy fold + Damerau: positives and the contradictions of those positives."""

from app.data.fuzzy import close_enough, damerau, fold, match_rank, ratio


def test_fold_puruliya_is_purulia():
    assert fold("Puruliya") == fold("Purulia") == "purulia"
    assert fold("purulia district") == "purulia"
    assert fold("Cherrapunjee").startswith("cherrapunj")


def test_fold_does_not_collapse_puri_into_purulia():
    assert fold("Puri") == "puri"
    assert fold("Purulia") == "purulia"
    assert fold("Puri") != fold("Purulia")


def test_damerau_transpose_and_identity():
    assert damerau("abc", "abc") == 0
    assert damerau("ab", "ba") == 1
    assert damerau("", "hi") == 2


def test_close_enough_known_romanizations():
    assert close_enough("Puruliya", "Purulia")
    assert close_enough("Cherrapunjee", "Cherrapunji")
    assert close_enough("Bengalooru", "Bengaluru")
    assert close_enough("calcuta", "calcutta")
    assert match_rank("Puruliya", "Purulia") == 0


def test_contradiction_close_enough_rejects_stems_and_cousins():
    """If Puruliya~Purulia passes, these near-misses must fail."""
    assert not close_enough("Puri", "Purulia")
    assert not close_enough("Purulia", "Puri")
    assert not close_enough("Pure", "Purulia")
    assert not close_enough("Pure", "Puri")
    assert not close_enough("Calicut", "Calcutta")
    assert not close_enough("Calcutta", "Calicut")
    assert not close_enough("Pune", "Puri")
    assert not close_enough("Pune", "Purulia")
    assert not close_enough("Cherry", "Cherrapunji")
    assert not close_enough("Cherry", "Cherra")
    assert close_enough("Cherra", "cherra")
    assert not close_enough("Bangor", "Bengaluru")
    assert not close_enough("Howrah", "Hogwarts")
    assert not close_enough("Nadia", "Narnia")
    assert not close_enough("Kochi", "Kolkata")
    assert not close_enough("Paris", "Patna")
    assert not close_enough("Paris", "Puri")
    assert match_rank("Puri", "Purulia") is None
    assert ratio("Puruliya", "Puri") < 0.85

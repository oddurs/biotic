"""The dish's physics: actions parse, cells eat and divide, the culture grows."""

from bio.culture import FALLBACK_GENESIS
from bio.dish import Dish, parse_action


def test_parse_action_coerces_genome_output():
    assert parse_action("eat") == ("eat", None)
    assert parse_action(None) == ("rest", None)
    assert parse_action("split") == ("divide", None)
    assert parse_action(("move", 11)) == ("move", 3)
    assert parse_action(("emit", 5)) == ("emit", 1.0)
    assert parse_action(True) is None
    assert parse_action("photosynthesize") is None


def test_founding_strain_grows_from_the_inoculum():
    dish = Dish("test", width=24, height=12)
    dish.register("f", FALLBACK_GENESIS)
    placed = dish.inoculate("f")
    assert placed == 5
    for _ in range(80):
        dish.step()
    assert dish.tick == 80
    assert dish.births > 0
    assert len(dish.cells) > placed
    assert dish.census() == {"f": len(dish.cells)}


def test_dish_round_trips_through_dict():
    dish = Dish("test", width=24, height=12)
    dish.register("f", FALLBACK_GENESIS)
    dish.inoculate("f")
    for _ in range(10):
        dish.step()
    clone = Dish.from_dict(dish.to_dict())
    assert clone.tick == dish.tick
    assert clone.census() == dish.census()
    assert clone.nutrient_mean() == dish.nutrient_mean()

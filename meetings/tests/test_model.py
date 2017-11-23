import model
import random
import arrow
import nose
import logging
logging.basicConfig(format='%(levelname)s:%(message)s',
                    level=logging.WARNING)
log = logging.getLogger(__name__)

range_day = 7
range_hour = 8

now = arrow.now()

now_min = now.format("mm")
now_hour = int(now.format('HH'))
then = now.shift(days=range_day, hours=range_hour)

then_min = then.format("mm")
RANGE = model.calendar_event(now.isoformat(), then.isoformat())

def test_without():

    test_case_start = now.shift(days=-1)
    test_case_end = test_case_start.shift(seconds=1)
    test_case = model.calendar_event(test_case_start, test_case_end)
    assert test_case.compare_to(RANGE) == model.event_compare_result.without

    test_case_start = now.shift(hours=-3)
    test_case_end = test_case_start.shift(hours=2)
    test_case = model.calendar_event(test_case_start, test_case_end)
    assert test_case.compare_to(RANGE) == model.event_compare_result.without

    test_case_start = then.shift(days=1)
    test_case_end = test_case_start.shift(hours=3)
    test_case = model.calendar_event(test_case_start, test_case_end)
    assert test_case.compare_to(RANGE) == model.event_compare_result.without

    for i in range(10000):
        test_case_start = now.shift(days=random.randrange(range_day))
        test_case_start = test_case_start.shift(hours=random.randrange(-(24-range_hour), -1))
        test_case_end = test_case_start.shift(hours=1)

        test_case = model.calendar_event(test_case_start, test_case_end)
        logging.info(str(test_case))
        assert test_case.compare_to(RANGE) == model.event_compare_result.without
        logging.info("Passed.")

        test_case_start = then.shift(days=random.randrange(-range_day, 0))
        test_case_start = test_case_end.shift(hours=random.randrange(1, (24-range_hour)))
        test_case_end = test_case_start.shift(hours=1)

        logging.info(str(test_case))
        assert test_case.compare_to(RANGE) == model.event_compare_result.without
        logging.info("Passed.")


def test_within():

    test_case_start = now.shift(days=1)
    test_case_end = test_case_start.shift(seconds=1)
    test_case = model.calendar_event(test_case_start, test_case_end)
    assert test_case.compare_to(RANGE) == model.event_compare_result.within

    test_case_start = now.shift(hours=-3)
    test_case_end = test_case_start.shift(hours=4)
    test_case = model.calendar_event(test_case_start, test_case_end)
    assert test_case.compare_to(RANGE) == model.event_compare_result.within

    test_case_start = then.shift(days=-1)
    test_case_end = test_case_start.shift(days=2)
    test_case = model.calendar_event(test_case_start, test_case_end)
    assert test_case.compare_to(RANGE) == model.event_compare_result.within

    for i in range(10000):
        test_case_start = now.shift(days=random.randrange(range_day))
        test_case_start = test_case_start.shift(hours=random.randrange(1, range_hour))
        test_case_end = test_case_start.shift(hours=1)

        test_case = model.calendar_event(test_case_start, test_case_end)
        logging.info(str(test_case))
        logging.info("Range: " + str(RANGE))
        assert test_case.compare_to(RANGE) == model.event_compare_result.within
        logging.info("Passed.")

        test_case_start = then.shift(days=random.randrange(-range_day, 0))
        test_case_start = test_case_end.shift(hours=random.randrange(1, range_hour))
        test_case_end = test_case_start.shift(hours=1)

        logging.info(str(test_case))
        assert test_case.compare_to(RANGE) == model.event_compare_result.within
        logging.info("Passed.")

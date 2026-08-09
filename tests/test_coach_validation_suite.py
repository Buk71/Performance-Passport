import datetime, unittest
from unittest.mock import patch
from core.coach_validation_suite import ValidationScenario,_asof_hard_effort,_infer_quality_days,simulate_scenario

class CoachValidationSuiteTests(unittest.TestCase):
    @patch("core.coach_validation_suite.get_connection")
    def test_quality_days_query_stops_at_start(self, connection):
        cursor=connection.return_value.cursor.return_value
        cursor.fetchall.return_value=[]
        start=datetime.date(2026,5,1)
        self.assertEqual(_infer_quality_days(1,start),(2,5))
        args=cursor.execute.call_args[0][1]
        self.assertEqual(args[2],start.isoformat())

    @patch("core.coach_validation_suite._prior_standard_paces")
    def test_asof_hard_effort_uses_prior_history(self, paces):
        paces.return_value=[230,232,234,236,240,245,250,255]
        self.assertTrue(_asof_hard_effort(1,datetime.date(2026,5,1),"Running",5.0,1145,1145))

    @patch("core.coach_validation_suite._prior_execution", return_value=[])
    @patch("core.coach_validation_suite._actual", return_value=None)
    @patch("core.coach_validation_suite._infer_quality_days", return_value=(2,5))
    def test_safe_spacing(self, days, actual, prior):
        r=simulate_scenario(ValidationScenario("x",1,"Test",datetime.date(2026,5,5),4,"ordinary"))
        self.assertEqual(r.review_count,0)

if __name__=="__main__": unittest.main()

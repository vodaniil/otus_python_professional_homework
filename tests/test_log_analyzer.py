import unittest
import json
import os
import log_analyzer

class TestLogAnalyzer (unittest.TestCase):
    def test_get_config (self):
        #self.assertRaises (ZeroDivisionError, log_analyzer.main)
        self.assertRaises (FileNotFoundError, log_analyzer.get_config, {}, "not_a_path")

if __name__ == '__main__':
    unittest.main()

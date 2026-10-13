import unittest

from src.data_collector import parse_serial_line


class SerialProtocolTests(unittest.TestCase):
    def test_parses_csi_json(self):
        measurement = parse_serial_line('{"type":"csi","seq":7,"t_us":42000,"rssi_dbm":-48,"amplitude":21.5}')
        self.assertIsNotNone(measurement)
        self.assertEqual(measurement.mode, "csi")
        self.assertEqual(measurement.sequence, 7)
        self.assertEqual(measurement.amplitude, 21.5)

    def test_parses_rssi_fallback(self):
        measurement = parse_serial_line('{"type":"rssi","seq":8,"t_us":52000,"rssi_dbm":-62}')
        self.assertIsNotNone(measurement)
        self.assertEqual(measurement.mode, "rssi")
        self.assertEqual(measurement.rssi_dbm, -62.0)
        self.assertIsNone(measurement.amplitude)

    def test_ignores_logs_malformed_and_invalid_values(self):
        self.assertIsNone(parse_serial_line("I (100) wifi: started"))
        self.assertIsNone(parse_serial_line("{not json}"))
        self.assertIsNone(parse_serial_line('{"type":"csi","rssi_dbm":-50,"amplitude":"nan"}'))


if __name__ == "__main__":
    unittest.main()

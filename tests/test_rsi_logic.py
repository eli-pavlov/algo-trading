import unittest
import pandas as pd
from src.strategies.rsi_panic import calculate_rsi

class TestRSILogic(unittest.TestCase):
    def test_rsi_calculation(self):
        # Create a mock price series (uptrend then crash)
        prices = [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 115, 110, 105, 100]
        series = pd.Series(prices)
        
        # Calculate RSI with a short period for testing
        rsi = calculate_rsi(series, period=6)
        
        # Check the last value
        last_rsi = rsi.iloc[-1]
        
        # In a crash, RSI should be low
        print(f"Calculated RSI: {last_rsi}")
        self.assertTrue(last_rsi < 30, "RSI should be oversold (<30) after this crash sequence")

if __name__ == '__main__':
    unittest.main()
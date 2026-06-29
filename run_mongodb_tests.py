import sys
sys.path.insert(0, '/app')

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openoutreach.settings.development')

import django
django.setup()

from tests.test_mongodb_models import *
import unittest

suite = unittest.TestLoader().loadTestsFromModule(sys.modules['test_mongodb_models'])
result = unittest.TextTestRunner(verbosity=2).run(suite)

# Print summary
print("\n" + "="*70)
print(f"Tests run: {result.testsRun}")
print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
print(f"Failures: {len(result.failures)}")
print(f"Errors: {len(result.errors)}")
print("="*70)

if result.failures:
    print("\nFAILURES:")
    for test, traceback in result.failures:
        print(f"\n{test}:")
        print(traceback)

if result.errors:
    print("\nERRORS:")
    for test, traceback in result.errors:
        print(f"\n{test}:")
        print(traceback)

sys.exit(0 if result.wasSuccessful() else 1)
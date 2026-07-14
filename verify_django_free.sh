#!/bin/bash

echo "=========================================="
echo "Django Elimination Verification Script"
echo "=========================================="
echo ""

echo "Checking for Django imports..."
echo ""

echo "1. Checking 'from django' imports:"
DJANGO_FROM=$(grep -r "from django" openoutreach --include="*.py" | grep -v __pycache__ | wc -l)
echo "   Count: $DJANGO_FROM"
if [ "$DJANGO_FROM" -eq 0 ]; then
    echo "   ✅ PASS - No 'from django' imports found"
else
    echo "   ❌ FAIL - Found $DJANGO_FROM 'from django' imports"
    grep -r "from django" openoutreach --include="*.py" | grep -v __pycache__
fi
echo ""

echo "2. Checking 'import django' statements:"
DJANGO_IMPORT=$(grep -r "import django" openoutreach --include="*.py" | grep -v __pycache__ | wc -l)
echo "   Count: $DJANGO_IMPORT"
if [ "$DJANGO_IMPORT" -eq 0 ]; then
    echo "   ✅ PASS - No 'import django' statements found"
else
    echo "   ❌ FAIL - Found $DJANGO_IMPORT 'import django' statements"
    grep -r "import django" openoutreach --include="*.py" | grep -v __pycache__
fi
echo ""

echo "3. Checking for Django-specific files:"
echo "   - apps.py files:"
APPS_COUNT=$(find openoutreach -name "apps.py" -type f | grep -v __pycache__ | wc -l)
echo "     Count: $APPS_COUNT"
if [ "$APPS_COUNT" -eq 0 ]; then
    echo "     ✅ PASS - No apps.py files found"
else
    echo "     ❌ FAIL - Found $APPS_COUNT apps.py files"
fi

echo "   - admin.py files:"
ADMIN_COUNT=$(find openoutreach -name "admin.py" -type f | grep -v __pycache__ | wc -l)
echo "     Count: $ADMIN_COUNT"
if [ "$ADMIN_COUNT" -eq 0 ]; then
    echo "     ✅ PASS - No admin.py files found"
else
    echo "     ❌ FAIL - Found $ADMIN_COUNT admin.py files"
fi

echo "   - management/commands directories:"
MGMT_COUNT=$(find openoutreach -type d -path "*/management/commands" | wc -l)
echo "     Count: $MGMT_COUNT"
if [ "$MGMT_COUNT" -eq 0 ]; then
    echo "     ✅ PASS - No management/commands directories found"
else
    echo "     ❌ FAIL - Found $MGMT_COUNT management/commands directories"
fi
echo ""

echo "4. Checking for legacy directories:"
echo "   - api_django_legacy:"
if [ ! -d "openoutreach/api_django_legacy" ]; then
    echo "     ✅ PASS - api_django_legacy directory deleted"
else
    echo "     ❌ FAIL - api_django_legacy directory still exists"
fi

echo "   - notifications:"
if [ ! -d "openoutreach/notifications" ]; then
    echo "     ✅ PASS - notifications directory deleted"
else
    echo "     ❌ FAIL - notifications directory still exists"
fi

echo "   - middleware:"
if [ ! -d "openoutreach/middleware" ]; then
    echo "     ✅ PASS - middleware directory deleted"
else
    echo "     ❌ FAIL - middleware directory still exists"
fi
echo ""

echo "=========================================="
echo "Summary"
echo "=========================================="

if [ "$DJANGO_FROM" -eq 0 ] && [ "$DJANGO_IMPORT" -eq 0 ] && \
   [ "$APPS_COUNT" -eq 0 ] && [ "$ADMIN_COUNT" -eq 0 ] && \
   [ "$MGMT_COUNT" -eq 0 ] && [ ! -d "openoutreach/api_django_legacy" ] && \
   [ ! -d "openoutreach/notifications" ] && [ ! -d "openoutreach/middleware" ]; then
    echo "✅ ALL CHECKS PASSED - Codebase is Django-free!"
else
    echo "❌ SOME CHECKS FAILED - Review output above"
fi
echo ""

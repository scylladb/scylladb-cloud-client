from pathlib import Path
import unittest


class PackagingTests(unittest.TestCase):
    def test_package_version_is_read_from_version_file(self):
        project_root = Path(__file__).resolve().parents[1]
        pyproject = (project_root / "pyproject.toml").read_text(encoding="utf-8")
        version = (project_root / "VERSION").read_text(encoding="utf-8").strip()

        self.assertEqual(version, "26.5.1")
        self.assertIn('dynamic = ["version"]', pyproject)
        self.assertIn('version = {file = "VERSION"}', pyproject)
        self.assertNotIn('version = "0.1.0"', pyproject)


if __name__ == "__main__":
    unittest.main()

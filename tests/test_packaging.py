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

    def test_package_exposes_scc_script_alias(self):
        project_root = Path(__file__).resolve().parents[1]
        pyproject = (project_root / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn('scylladb-cloud-client = "scylladb_cloud_client.cli:main"', pyproject)
        self.assertIn('scc = "scylladb_cloud_client.cli:main"', pyproject)

    def test_installer_and_uninstaller_manage_scc_alias_symlink(self):
        project_root = Path(__file__).resolve().parents[1]
        install_script = (project_root / "install.sh").read_text(encoding="utf-8")
        uninstall_script = (project_root / "uninstall.sh").read_text(encoding="utf-8")

        self.assertIn('BIN_ALIAS="${BIN_DIR}/scc"', install_script)
        self.assertIn('ln -sf "${BIN_LINK}" "${BIN_ALIAS}"', install_script)
        self.assertIn('BIN_ALIAS="${PREFIX}/bin/scc"', uninstall_script)
        self.assertIn('rm "${BIN_ALIAS}"', uninstall_script)


if __name__ == "__main__":
    unittest.main()

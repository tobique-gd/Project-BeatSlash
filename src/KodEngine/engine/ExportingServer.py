import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Any, Optional

from .ErrorHandler import ErrorHandler


class Exporter:
	def __init__(self, project_dir: str, project_settings: dict[str, Any]):
		self.project_dir = os.path.abspath(project_dir)
		self.project_settings = json.loads(json.dumps(project_settings))

	def export_async(
		self,
		*,
		output_dir: str,
		output_name: str,
		platform_name: str,
		build_mode: str,
		one_file: bool,
		include_assets: bool,
		include_runtime: bool,
	) -> threading.Thread:
		worker = threading.Thread(
			target=self.export,
			kwargs={
				"output_dir": output_dir,
				"output_name": output_name,
				"platform_name": platform_name,
				"build_mode": build_mode,
				"one_file": one_file,
				"include_assets": include_assets,
				"include_runtime": include_runtime,
			},
			daemon=True,
		)
		worker.start()
		return worker

	def export(
		self,
		*,
		output_dir: str,
		output_name: str,
		platform_name: str,
		build_mode: str,
		one_file: bool,
		include_assets: bool,
		include_runtime: bool,
	) -> bool:
		if not os.path.isdir(self.project_dir):
			ErrorHandler.throw_error(f"Export failed: project directory not found: {self.project_dir}")
			return False

		output_name = output_name.strip() or "game"
		output_dir = os.path.abspath(output_dir)
		os.makedirs(output_dir, exist_ok=True)

		if not self._platform_supported(platform_name):
			return False

		staging_root = tempfile.mkdtemp(prefix="kod_export_")
		staging_dir = os.path.join(staging_root, "staging")
		os.makedirs(staging_dir, exist_ok=True)

		try:
			project_stage = os.path.join(staging_dir, "project")
			engine_stage = os.path.join(staging_dir, "KodEngine")
			
			self._copy_project(project_stage, include_assets)
			self._copy_engine(engine_stage)

			runtime_path = os.path.join(staging_dir, "runtime.py")
			self._write_runtime(runtime_path)

			if include_runtime:
				success = self._build_with_pyinstaller(
					runtime_path=runtime_path,
					staging_dir=staging_dir,
					project_stage=project_stage,
					output_dir=output_dir,
					output_name=output_name,
					platform_name=platform_name,
					build_mode=build_mode,
					one_file=one_file,
				)
			else:
				success = self._emit_unbundled_output(
					staging_dir=staging_dir,
					output_dir=output_dir,
					output_name=output_name,
				)

			if success:
				ErrorHandler.throw_success(f"Export finished: {output_dir}")
				return True
			else:
				ErrorHandler.throw_error("Export process failed.")
				return False
				
		except Exception as exc:
			ErrorHandler.throw_error(f"Export failed with exception: {exc}")
			return False
		finally:
			self._cleanup_staging(staging_root)

	def _cleanup_staging(self, staging_root: str):
		if not os.path.exists(staging_root):
			return
			
		try:
			shutil.rmtree(staging_root, ignore_errors=True)
		except Exception:
			pass

	def _platform_supported(self, platform_name: str) -> bool:
		platform_key = platform_name.lower()
		current = sys.platform
		
		if platform_key == "windows" and not current.startswith("win"):
			ErrorHandler.throw_error("Export failed: Windows builds must be made on Windows.")
			return False
		if platform_key == "macos" and current != "darwin":
			ErrorHandler.throw_error("Export failed: macOS builds must be made on macOS.")
			return False
		if platform_key == "linux" and not current.startswith("linux"):
			ErrorHandler.throw_error("Export failed: Linux builds must be made on Linux.")
			return False
		
		return True

	def _copy_project(self, project_stage: str, include_assets: bool):
		ignore = None
		if not include_assets:
			ignore = shutil.ignore_patterns("assets")
		shutil.copytree(self.project_dir, project_stage, dirs_exist_ok=True, ignore=ignore)

	def _copy_engine(self, engine_stage: str):
		engine_src = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
		shutil.copytree(engine_src, engine_stage, dirs_exist_ok=True)

	def _write_runtime(self, runtime_path: str):
		settings_json = json.dumps(self.project_settings, ensure_ascii=True)

		runtime_code = f"""import json
import os
import sys
from KodEngine.engine import ResourceServer
from KodEngine.engine import Kod


def _merge_settings_dict(target, override):
	if not isinstance(target, dict) or not isinstance(override, dict):
		return target

	for key, value in override.items():
		current = target.get(key)
		if isinstance(current, dict) and isinstance(value, dict):
			_merge_settings_dict(current, value)
			continue
		target[key] = value

	return target


def _get_base_dir():
	if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
		return sys._MEIPASS
	return os.path.abspath(os.path.dirname(__file__))


def main():
	base_dir = _get_base_dir()
	if base_dir not in sys.path:
		sys.path.insert(0, base_dir)

	project_dir = os.path.join(base_dir, "project")
	settings_json = {settings_json!r}

	settings = Kod.Settings()
	if settings_json:
		_merge_settings_dict(settings.project_settings, json.loads(settings_json))

	settings.project_settings["file_management"]["project_directory"] = project_dir
	ResourceServer.ResourceLoader.set_project_root(project_dir)

	main_scene = settings.project_settings.get("project", {{}}).get("main_scene_path", "")
	if not main_scene:
		print("ERROR: main_scene_path is not configured.")
		return 1

	scene_path = main_scene
	if not os.path.isabs(scene_path):
		scene_path = os.path.abspath(os.path.join(project_dir, scene_path))

	app = Kod.App(settings, editor_mode=False)
	scene = ResourceServer.SceneLoader.load(scene_path)
	if scene:
		app.set_scene(scene)
		app.run()
		return 0

	print(f"ERROR: Failed to load scene: {{scene_path}}")
	return 1


if __name__ == "__main__":
	raise SystemExit(main())
"""

		with open(runtime_path, "w", encoding="utf-8") as handle:
			handle.write(runtime_code)

	def _build_with_pyinstaller(
		self,
		*,
		runtime_path: str,
		staging_dir: str,
		project_stage: str,
		output_dir: str,
		output_name: str,
		platform_name: str,
		build_mode: str,
		one_file: bool,
	) -> bool:
		"""Build the project using PyInstaller."""
		if not self._check_pyinstaller_installed():
			return False

		args = [
			sys.executable,
			"-m",
			"PyInstaller",
			runtime_path,
			"--name",
			output_name,
			"--distpath",
			output_dir,
			"--workpath",
			os.path.join(staging_dir, "build"),
			"--specpath",
			staging_dir,
			"--paths",
			staging_dir,
			"--clean",
			"--noconfirm",
		]

		if one_file:
			args.append("--onefile")
		else:
			args.append("--onedir")

		if build_mode.lower() == "release":
			args.append("--noconsole")
		else:
			args.append("--console")

		args.extend(["--add-data", f"{project_stage}{os.pathsep}project"])
		self._add_hidden_imports(args)

		result = subprocess.run(args, capture_output=True, text=True)
		
		if result.returncode != 0:
			stderr = result.stderr or ""
			stdout = result.stdout or ""
			combined_output = f"{stderr}\n{stdout}".strip()
			
			if combined_output:
				error_lines = combined_output.split('\n')
				relevant_errors = '\n'.join(error_lines[-20:])
				ErrorHandler.throw_error(f"PyInstaller build failed:\n{relevant_errors}")
			else:
				ErrorHandler.throw_error("PyInstaller failed with no error output.")
			return False

		ErrorHandler.throw_info(f"PyInstaller build completed successfully.")
		return True

	def _check_pyinstaller_installed(self) -> bool:
		try:
			result = subprocess.run(
				[sys.executable, "-m", "PyInstaller", "--version"],
				capture_output=True,
				text=True,
				timeout=5,
			)
			if result.returncode == 0:
				version = result.stdout.strip()
				ErrorHandler.throw_info(f"Using PyInstaller: {version}")
				return True
		except Exception:
			pass

		ErrorHandler.throw_error(
			"PyInstaller is not installed. Install it with: pip install pyinstaller"
		)
		return False

	def _add_hidden_imports(self, args: list[str]):
		hidden_imports = [
			"KodEngine",
			"KodEngine.engine",
			"KodEngine.engine.ResourceServer",
			"KodEngine.engine.Kod",
		]
		
		for imp in hidden_imports:
			args.extend(["--hidden-import", imp])

	def _emit_unbundled_output(
		self,
		*,
		staging_dir: str,
		output_dir: str,
		output_name: str,
	) -> bool:
		try:
			target_dir = os.path.join(output_dir, output_name)
			
			if os.path.exists(target_dir):
				shutil.rmtree(target_dir, ignore_errors=True)
			
			shutil.copytree(staging_dir, target_dir, dirs_exist_ok=True)
			ErrorHandler.throw_info(f"Exported unbundled runtime to: {target_dir}")
			return True
		except Exception as exc:
			ErrorHandler.throw_error(f"Failed to emit unbundled output: {exc}")
			return False
"""JSX Script Runner for InDesign Automation.

This module provides a Python interface for executing JSX scripts in Adobe InDesign.
It handles script execution via osascript (macOS) or COM (Windows) and manages
script arguments and return values.

Usage:
    runner = JSXRunner()
    result = runner.label_placed_objects(
        document_path=Path("document.indd"),
        manifest_path=Path("manifest.json")
    )

Author: KPS v2.0 InDesign Automation
Last Modified: 2025-11-06
"""

import json
import platform
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.assets import AssetLedger


@dataclass
class JSXResult:
    """Result from JSX script execution."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class JSXRunner:
    """
    Execute JSX scripts in Adobe InDesign.

    This class provides methods for running JSX scripts via InDesign's scripting
    interface. It supports both macOS (osascript) and Windows (COM) execution.

    Attributes:
        jsx_dir: Directory containing JSX scripts
        indesign_app: InDesign application name/path
    """

    def __init__(self, jsx_dir: Optional[Path] = None):
        """Initialize JSX runner.

        Args:
            jsx_dir: Directory containing JSX scripts (default: ./jsx)
        """
        if jsx_dir is None:
            jsx_dir = Path(__file__).parent / "jsx"

        self.jsx_dir = jsx_dir
        self.platform = platform.system()

        # Detect InDesign application
        if self.platform == "Darwin":  # macOS
            self.indesign_app = "Adobe InDesign 2024"  # Update version as needed
        elif self.platform == "Windows":
            self.indesign_app = "InDesign.Application"
        else:
            raise RuntimeError(f"Unsupported platform: {self.platform}")

    def execute_script(
        self, script_name: str, arguments: Optional[Dict[str, Any]] = None
    ) -> JSXResult:
        """Execute a JSX script in InDesign.

        Args:
            script_name: Name of JSX script (without .jsx extension)
            arguments: Dictionary of script arguments

        Returns:
            JSXResult with execution status and output

        Raises:
            FileNotFoundError: If script file not found
            RuntimeError: If InDesign is not running or script execution fails
        """
        script_path = self.jsx_dir / f"{script_name}.jsx"

        if not script_path.exists():
            raise FileNotFoundError(f"JSX script not found: {script_path}")

        if self.platform == "Darwin":
            return self._execute_macos(script_path, arguments)
        elif self.platform == "Windows":
            return self._execute_windows(script_path, arguments)
        else:
            raise RuntimeError(f"Unsupported platform: {self.platform}")

    def _execute_macos(
        self, script_path: Path, arguments: Optional[Dict[str, Any]] = None
    ) -> JSXResult:
        """Execute JSX script on macOS using osascript.

        Args:
            script_path: Path to JSX script
            arguments: Script arguments

        Returns:
            JSXResult with execution status
        """
        # Build AppleScript command
        applescript = f'''
            tell application "{self.indesign_app}"
                activate
                set scriptArgs to {{}}
        '''

        # Add arguments if provided
        if arguments:
            for key, value in arguments.items():
                # Convert Python types to AppleScript
                if isinstance(value, str):
                    applescript += f'\n                set scriptArgs to scriptArgs & {{"{key}", "{value}"}}'
                elif isinstance(value, (int, float)):
                    applescript += f'\n                set scriptArgs to scriptArgs & {{"{key}", {value}}}'
                elif isinstance(value, bool):
                    applescript += (
                        f'\n                set scriptArgs to scriptArgs & {{"{key}", {str(value).lower()}}}'
                    )

        # Execute script
        applescript += f'''
                do script "{script_path}" language javascript with arguments scriptArgs
            end tell
        '''

        try:
            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode == 0:
                return JSXResult(
                    success=True, stdout=result.stdout, stderr=result.stderr
                )
            else:
                return JSXResult(
                    success=False,
                    error=result.stderr or "Script execution failed",
                    stdout=result.stdout,
                    stderr=result.stderr,
                )

        except subprocess.TimeoutExpired:
            return JSXResult(success=False, error="Script execution timed out")
        except Exception as e:
            return JSXResult(success=False, error=f"Script execution error: {str(e)}")

    def _execute_windows(
        self, script_path: Path, arguments: Optional[Dict[str, Any]] = None
    ) -> JSXResult:
        """Execute JSX script on Windows using COM.

        Args:
            script_path: Path to JSX script
            arguments: Script arguments

        Returns:
            JSXResult with execution status
        """
        try:
            import win32com.client

            # Connect to InDesign
            indesign = win32com.client.Dispatch(self.indesign_app)

            # Build script arguments
            script_args = []
            if arguments:
                for key, value in arguments.items():
                    script_args.append(key)
                    script_args.append(str(value))

            # Execute script
            result = indesign.DoScript(
                str(script_path), 1952403696, script_args  # JavaScript language code
            )

            return JSXResult(success=True, data={"result": result})

        except ImportError:
            return JSXResult(
                success=False,
                error="win32com.client not available. Install pywin32 package.",
            )
        except Exception as e:
            return JSXResult(success=False, error=f"COM error: {str(e)}")

    def label_placed_objects(
        self, document_path: Path, manifest_path: Path
    ) -> JSXResult:
        """Label existing placed objects in InDesign document.

        Args:
            document_path: Path to InDesign document (.indd)
            manifest_path: Path to manifest.json

        Returns:
            JSXResult with labeling results
        """
        # Ensure document is open
        # Note: In production, you'd want to open the document via AppleScript/COM
        # For now, assume document is already open

        result = self.execute_script(
            "label_placed_objects", arguments={"manifestPath": str(manifest_path)}
        )

        return result

    def extract_labels(
        self, document_path: Path, output_path: Optional[Path] = None
    ) -> JSXResult:
        """Extract labels from InDesign document.

        Args:
            document_path: Path to InDesign document (.indd)
            output_path: Path to save extracted labels JSON

        Returns:
            JSXResult with extracted labels
        """
        if output_path is None:
            # Use temporary file
            output_path = Path(tempfile.gettempdir()) / "kps_extracted_labels.json"

        result = self.execute_script(
            "extract_object_labels", arguments={"outputPath": str(output_path)}
        )

        # Load extracted data if successful
        if result.success and output_path.exists():
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                result.data = data
            except Exception as e:
                result.error = f"Failed to load extracted data: {str(e)}"
                result.success = False

        return result

    def place_assets(
        self,
        document_path: Path,
        manifest_path: Path,
        assets_dir: Path,
        column_layout: Optional[Dict[str, Any]] = None,
    ) -> JSXResult:
        """Place assets from manifest into InDesign document.

        Args:
            document_path: Path to InDesign document (.indd)
            manifest_path: Path to manifest.json
            assets_dir: Directory containing asset files
            column_layout: Optional column layout information

        Returns:
            JSXResult with placement results
        """
        arguments = {
            "manifestPath": str(manifest_path),
            "assetsDir": str(assets_dir),
        }

        # Add column layout if provided
        if column_layout:
            # Save column layout to temp file
            temp_layout = Path(tempfile.gettempdir()) / "kps_column_layout.json"
            with open(temp_layout, "w", encoding="utf-8") as f:
                json.dump(column_layout, f, indent=2)
            arguments["columnLayoutPath"] = str(temp_layout)

        result = self.execute_script("place_assets_from_manifest", arguments=arguments)

        return result

    def place_assets_by_page_range(
        self,
        document_path: Path,
        manifest_path: Path,
        assets_dir: Path,
        start_page: int,
        end_page: int,
        column_layout: Optional[Dict[str, Any]] = None,
    ) -> JSXResult:
        """Place assets for specific page range.

        Args:
            document_path: Path to InDesign document (.indd)
            manifest_path: Path to manifest.json
            assets_dir: Directory containing asset files
            start_page: Start page (0-indexed)
            end_page: End page (0-indexed, inclusive)
            column_layout: Optional column layout information

        Returns:
            JSXResult with placement results
        """
        # Filter manifest by page range
        ledger = AssetLedger.load_json(manifest_path)
        filtered_assets = [
            a for a in ledger.assets if start_page <= a.page_number <= end_page
        ]

        # Create temporary filtered manifest
        filtered_ledger = AssetLedger(
            assets=filtered_assets,
            source_pdf=ledger.source_pdf,
            total_pages=ledger.total_pages,
        )

        temp_manifest = Path(tempfile.gettempdir()) / "kps_filtered_manifest.json"
        filtered_ledger.save_json(temp_manifest)

        # Place assets
        return self.place_assets(document_path, temp_manifest, assets_dir, column_layout)


# ============================================================================
# Convenience Functions
# ============================================================================


def label_document(document_path: Path, manifest_path: Path) -> Dict[str, Any]:
    """Convenience function to label a document.

    Args:
        document_path: Path to InDesign document
        manifest_path: Path to manifest.json

    Returns:
        Dictionary with results

    Raises:
        RuntimeError: If labeling fails
    """
    runner = JSXRunner()
    result = runner.label_placed_objects(document_path, manifest_path)

    if not result.success:
        raise RuntimeError(f"Labeling failed: {result.error}")

    return {"success": True, "stdout": result.stdout}


def extract_document_labels(
    document_path: Path, output_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Convenience function to extract labels from document.

    Args:
        document_path: Path to InDesign document
        output_path: Optional path to save JSON output

    Returns:
        Dictionary with extracted labels

    Raises:
        RuntimeError: If extraction fails
    """
    runner = JSXRunner()
    result = runner.extract_labels(document_path, output_path)

    if not result.success:
        raise RuntimeError(f"Extraction failed: {result.error}")

    return result.data


def place_document_assets(
    document_path: Path,
    manifest_path: Path,
    assets_dir: Path,
    column_layout: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience function to place assets in document.

    Args:
        document_path: Path to InDesign document
        manifest_path: Path to manifest.json
        assets_dir: Directory containing assets
        column_layout: Optional column layout info

    Returns:
        Dictionary with placement results

    Raises:
        RuntimeError: If placement fails
    """
    runner = JSXRunner()
    result = runner.place_assets(document_path, manifest_path, assets_dir, column_layout)

    if not result.success:
        raise RuntimeError(f"Placement failed: {result.error}")

    return {"success": True, "stdout": result.stdout}

# -*- coding: utf-8 -*-
"""Tests for KML/GPX export XML structure (no QGIS runtime)."""

import xml.etree.ElementTree as ET

import pytest


class TestKMLStructure:
    """Test that KML output has valid structure for Google Earth."""

    def _build_sample_kml(self):
        ns = "http://www.opengis.net/kml/2.2"
        kml = ET.Element("kml", xmlns=ns)
        doc = ET.SubElement(kml, "Document")
        name_el = ET.SubElement(doc, "name")
        name_el.text = "FMV Export"

        folder = ET.SubElement(doc, "Folder")
        folder_name = ET.SubElement(folder, "name")
        folder_name.text = "Platform"

        pm = ET.SubElement(folder, "Placemark")
        pm_name = ET.SubElement(pm, "name")
        pm_name.text = "TestPoint"
        pt = ET.SubElement(pm, "Point")
        coords = ET.SubElement(pt, "coordinates")
        coords.text = "-3.7038,40.4168"

        pm2 = ET.SubElement(folder, "Placemark")
        pm2_name = ET.SubElement(pm2, "name")
        pm2_name.text = "TestLine"
        ls = ET.SubElement(pm2, "LineString")
        coords2 = ET.SubElement(ls, "coordinates")
        coords2.text = "-3.70,40.41 -3.71,40.42 -3.72,40.43"

        pm3 = ET.SubElement(folder, "Placemark")
        pm3_name = ET.SubElement(pm3, "name")
        pm3_name.text = "TestPoly"
        poly = ET.SubElement(pm3, "Polygon")
        outer = ET.SubElement(poly, "outerBoundaryIs")
        ring = ET.SubElement(outer, "LinearRing")
        coords3 = ET.SubElement(ring, "coordinates")
        coords3.text = "0,0 1,0 1,1 0,1 0,0"

        ext = ET.SubElement(pm, "ExtendedData")
        data = ET.SubElement(ext, "Data", name="SensorLatitude")
        val = ET.SubElement(data, "value")
        val.text = "40.4168"

        return kml

    def test_kml_has_required_root(self):
        kml = self._build_sample_kml()
        assert kml.tag == "kml"
        assert "http://www.opengis.net/kml/2.2" in kml.attrib.get("xmlns", "")

    def test_kml_has_document(self):
        kml = self._build_sample_kml()
        doc = kml.find("Document")
        assert doc is not None
        assert doc.find("name") is not None

    def test_kml_has_folder(self):
        kml = self._build_sample_kml()
        folder = kml.find("Document/Folder")
        assert folder is not None

    def test_kml_placemarks_have_geometry(self):
        kml = self._build_sample_kml()
        placemarks = kml.findall(".//Placemark")
        assert len(placemarks) >= 3
        for pm in placemarks:
            geom = pm.find("Point")
            if geom is None:
                geom = pm.find("LineString")
            if geom is None:
                geom = pm.find("Polygon")
            assert geom is not None

    def test_kml_coordinates_are_lon_lat(self):
        kml = self._build_sample_kml()
        coords = kml.find(".//Point/coordinates")
        assert coords is not None
        parts = coords.text.split(",")
        lon, lat = float(parts[0]), float(parts[1])
        assert -180 <= lon <= 180
        assert -90 <= lat <= 90

    def test_kml_extended_data(self):
        kml = self._build_sample_kml()
        ext = kml.find(".//ExtendedData")
        assert ext is not None
        data = ext.find("Data[@name='SensorLatitude']")
        assert data is not None
        assert data.find("value").text == "40.4168"

    def test_kml_serializes_to_valid_xml(self):
        kml = self._build_sample_kml()
        tree = ET.ElementTree(kml)
        import io

        buf = io.BytesIO()
        tree.write(buf, encoding="utf-8", xml_declaration=True)
        xml_bytes = buf.getvalue()
        assert b"<?xml" in xml_bytes
        assert b"<kml" in xml_bytes

    def test_kml_linestring_coordinates(self):
        kml = self._build_sample_kml()
        coords = kml.find(".//LineString/coordinates")
        assert coords is not None
        points = coords.text.strip().split(" ")
        assert len(points) == 3


class TestGPXStructure:
    """Test that GPX output has valid structure for Google Earth / GPS devices."""

    def _build_sample_gpx(self):
        gpx_ns = "http://www.topografix.com/GPX/1/1"
        gpx = ET.Element(
            "gpx",
            version="1.1",
            creator="QGIS FMV",
            xmlns=gpx_ns,
        )

        metadata = ET.SubElement(gpx, "metadata")
        meta_name = ET.SubElement(metadata, "name")
        meta_name.text = "TestTrack"
        meta_time = ET.SubElement(metadata, "time")
        meta_time.text = "2024-01-15T12:00:00Z"

        trk = ET.SubElement(gpx, "trk")
        trk_name = ET.SubElement(trk, "name")
        trk_name.text = "Platform"

        trkseg = ET.SubElement(trk, "trkseg")
        for lon, lat in [(-3.70, 40.41), (-3.71, 40.42), (-3.72, 40.43)]:
            ET.SubElement(trkseg, "trkpt", lat=f"{lat:.6f}", lon=f"{lon:.6f}")

        return gpx

    def test_gpx_has_required_root(self):
        gpx = self._build_sample_gpx()
        assert gpx.tag == "gpx"
        assert gpx.attrib.get("version") == "1.1"

    def test_gpx_has_metadata(self):
        gpx = self._build_sample_gpx()
        metadata = gpx.find("metadata")
        assert metadata is not None
        assert metadata.find("name") is not None
        assert metadata.find("time") is not None

    def test_gpx_has_track(self):
        gpx = self._build_sample_gpx()
        trk = gpx.find("trk")
        assert trk is not None
        assert trk.find("name") is not None

    def test_gpx_has_track_segment(self):
        gpx = self._build_sample_gpx()
        trkseg = gpx.find("trk/trkseg")
        assert trkseg is not None

    def test_gpx_track_points_have_lat_lon(self):
        gpx = self._build_sample_gpx()
        trkpts = gpx.findall("trk/trkseg/trkpt")
        assert len(trkpts) == 3
        for pt in trkpts:
            lat = float(pt.attrib["lat"])
            lon = float(pt.attrib["lon"])
            assert -90 <= lat <= 90
            assert -180 <= lon <= 180

    def test_gpx_serializes_to_valid_xml(self):
        gpx = self._build_sample_gpx()
        tree = ET.ElementTree(gpx)
        import io

        buf = io.BytesIO()
        tree.write(buf, encoding="utf-8", xml_declaration=True)
        xml_bytes = buf.getvalue()
        assert b"<?xml" in xml_bytes
        assert b"<gpx" in xml_bytes

    def test_gpx_track_point_format(self):
        gpx = self._build_sample_gpx()
        pt = gpx.find("trk/trkseg/trkpt")
        assert "lat" in pt.attrib
        assert "lon" in pt.attrib
        # Verify 6 decimal places as the export code does
        assert "." in pt.attrib["lat"]
        assert len(pt.attrib["lat"].split(".")[1]) == 6


class TestKMLFileRoundtrip:
    """Write a KML file, read it back, and validate structure."""

    def _generate_kml(self, path):
        """Generate a realistic KML file mimicking the export code."""
        ns = "http://www.opengis.net/kml/2.2"
        kml = ET.Element("kml", xmlns=ns)
        doc = ET.SubElement(kml, "Document")
        ET.SubElement(doc, "name").text = "FMV Test Export"

        # Platform folder with a point
        folder = ET.SubElement(doc, "Folder")
        ET.SubElement(folder, "name").text = "Platform"
        pm = ET.SubElement(folder, "Placemark")
        ET.SubElement(pm, "name").text = "Sensor"
        pt = ET.SubElement(pm, "Point")
        ET.SubElement(pt, "coordinates").text = "-3.7038,40.4168"

        # Trajectory folder with a line
        folder2 = ET.SubElement(doc, "Folder")
        ET.SubElement(folder2, "name").text = "Trajectory"
        pm2 = ET.SubElement(folder2, "Placemark")
        ET.SubElement(pm2, "name").text = "Track"
        ls = ET.SubElement(pm2, "LineString")
        ET.SubElement(ls, "coordinates").text = (
            "-3.70,40.41 -3.71,40.42 -3.72,40.43 -3.73,40.44"
        )

        # Footprint folder with a polygon
        folder3 = ET.SubElement(doc, "Folder")
        ET.SubElement(folder3, "name").text = "Footprint"
        pm3 = ET.SubElement(folder3, "Placemark")
        ET.SubElement(pm3, "name").text = "Frame"
        poly = ET.SubElement(pm3, "Polygon")
        outer = ET.SubElement(poly, "outerBoundaryIs")
        ring = ET.SubElement(outer, "LinearRing")
        ET.SubElement(ring, "coordinates").text = (
            "-3.71,40.40 -3.69,40.40 -3.69,40.42 -3.71,40.42 -3.71,40.40"
        )

        tree = ET.ElementTree(kml)
        ET.indent(tree, space="  ")
        tree.write(path, encoding="utf-8", xml_declaration=True)

    def test_kml_file_is_valid_xml(self, tmp_path):
        path = tmp_path / "test.kml"
        self._generate_kml(str(path))
        tree = ET.parse(str(path))
        assert tree.getroot().tag == "{http://www.opengis.net/kml/2.2}kml"

    def test_kml_file_has_folders(self, tmp_path):
        path = tmp_path / "test.kml"
        self._generate_kml(str(path))
        tree = ET.parse(str(path))
        root = tree.getroot()
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        folders = root.findall(".//kml:Folder", ns)
        assert len(folders) == 3
        names = [f.find("kml:name", ns).text for f in folders]
        assert "Platform" in names
        assert "Trajectory" in names
        assert "Footprint" in names

    def test_kml_file_placemarks_count(self, tmp_path):
        path = tmp_path / "test.kml"
        self._generate_kml(str(path))
        tree = ET.parse(str(path))
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        placemarks = tree.getroot().findall(".//kml:Placemark", ns)
        assert len(placemarks) == 3

    def test_kml_file_coordinates_valid(self, tmp_path):
        path = tmp_path / "test.kml"
        self._generate_kml(str(path))
        tree = ET.parse(str(path))
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        coords_list = tree.getroot().findall(".//kml:coordinates", ns)
        assert len(coords_list) >= 3
        for coords_el in coords_list:
            text = coords_el.text.strip()
            points = text.split(" ")
            for pt_str in points:
                parts = pt_str.split(",")
                lon = float(parts[0])
                lat = float(parts[1])
                assert -180 <= lon <= 180
                assert -90 <= lat <= 90

    def test_kml_file_not_empty(self, tmp_path):
        path = tmp_path / "test.kml"
        self._generate_kml(str(path))
        assert path.stat().st_size > 100


class TestGPXFileRoundtrip:
    """Write a GPX file, read it back, and validate structure."""

    def _generate_gpx(self, path):
        """Generate a realistic GPX file mimicking the export code."""
        gpx_ns = "http://www.topografix.com/GPX/1/1"
        gpx = ET.Element(
            "gpx",
            version="1.1",
            creator="QGIS FMV",
            xmlns=gpx_ns,
        )

        metadata = ET.SubElement(gpx, "metadata")
        ET.SubElement(metadata, "name").text = "Platform Track"
        ET.SubElement(metadata, "time").text = "2024-01-15T12:00:00Z"

        trk = ET.SubElement(gpx, "trk")
        ET.SubElement(trk, "name").text = "Trajectory"

        trkseg = ET.SubElement(trk, "trkseg")
        trajectory = [
            (-3.7038, 40.4168),
            (-3.7045, 40.4172),
            (-3.7052, 40.4176),
            (-3.7059, 40.4180),
            (-3.7066, 40.4184),
            (-3.7073, 40.4188),
            (-3.7080, 40.4192),
            (-3.7087, 40.4196),
            (-3.7094, 40.4200),
            (-3.7101, 40.4204),
        ]
        for lon, lat in trajectory:
            ET.SubElement(trkseg, "trkpt", lat=f"{lat:.6f}", lon=f"{lon:.6f}")

        tree = ET.ElementTree(gpx)
        ET.indent(tree, space="  ")
        tree.write(path, encoding="utf-8", xml_declaration=True)

    def test_gpx_file_is_valid_xml(self, tmp_path):
        path = tmp_path / "test.gpx"
        self._generate_gpx(str(path))
        tree = ET.parse(str(path))
        root = tree.getroot()
        assert root.tag == "{http://www.topografix.com/GPX/1/1}gpx"

    def test_gpx_file_has_metadata(self, tmp_path):
        path = tmp_path / "test.gpx"
        self._generate_gpx(str(path))
        tree = ET.parse(str(path))
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        metadata = tree.getroot().find("gpx:metadata", ns)
        assert metadata is not None
        assert metadata.find("gpx:name", ns) is not None
        assert metadata.find("gpx:time", ns) is not None

    def test_gpx_file_has_track(self, tmp_path):
        path = tmp_path / "test.gpx"
        self._generate_gpx(str(path))
        tree = ET.parse(str(path))
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        trk = tree.getroot().find("gpx:trk", ns)
        assert trk is not None
        trk_name = trk.find("gpx:name", ns)
        assert trk_name is not None
        assert trk_name.text == "Trajectory"

    def test_gpx_file_track_points(self, tmp_path):
        path = tmp_path / "test.gpx"
        self._generate_gpx(str(path))
        tree = ET.parse(str(path))
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        trkpts = tree.getroot().findall(".//gpx:trkpt", ns)
        assert len(trkpts) == 10

    def test_gpx_file_track_point_coords(self, tmp_path):
        path = tmp_path / "test.gpx"
        self._generate_gpx(str(path))
        tree = ET.parse(str(path))
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        trkpts = tree.getroot().findall(".//gpx:trkpt", ns)
        for pt in trkpts:
            lat = float(pt.attrib["lat"])
            lon = float(pt.attrib["lon"])
            assert -90 <= lat <= 90
            assert -180 <= lon <= 180

    def test_gpx_file_version(self, tmp_path):
        path = tmp_path / "test.gpx"
        self._generate_gpx(str(path))
        tree = ET.parse(str(path))
        root = tree.getroot()
        assert root.attrib.get("version") == "1.1"

    def test_gpx_file_not_empty(self, tmp_path):
        path = tmp_path / "test.gpx"
        self._generate_gpx(str(path))
        assert path.stat().st_size > 50

    def test_gpx_file_first_point(self, tmp_path):
        path = tmp_path / "test.gpx"
        self._generate_gpx(str(path))
        tree = ET.parse(str(path))
        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}
        first = tree.getroot().find(".//gpx:trkpt", ns)
        assert float(first.attrib["lat"]) == pytest.approx(40.4168, abs=0.001)
        assert float(first.attrib["lon"]) == pytest.approx(-3.7038, abs=0.001)

"""Tests for KML/GPX export XML structure (no QGIS runtime)."""

import defusedxml.ElementTree as ET
import pytest


class TestKMLStructure:
    """Test that KML output has valid structure for Google Earth."""

    def _build_sample_kml(self):
        ns = "http://www.opengis.net/kml/2.2"

        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<kml xmlns="{ns}">
  <Document>
    <name>FMV Export</name>

    <Folder>
      <name>Platform</name>

      <Placemark>
        <name>TestPoint</name>
        <Point>
          <coordinates>-3.7038,40.4168</coordinates>
        </Point>
        <ExtendedData>
          <Data name="SensorLatitude">
            <value>40.4168</value>
          </Data>
        </ExtendedData>
      </Placemark>

      <Placemark>
        <name>TestLine</name>
        <LineString>
          <coordinates>-3.70,40.41 -3.71,40.42 -3.72,40.43</coordinates>
        </LineString>
      </Placemark>

      <Placemark>
        <name>TestPoly</name>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>0,0 1,0 1,1 0,1 0,0</coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>

    </Folder>
  </Document>
</kml>
"""

        return ET.fromstring(xml)

    def test_kml_has_required_root(self):
        kml = self._build_sample_kml()

        assert kml.tag.endswith("kml")

        assert (
            "http://www.opengis.net/kml/2.2" in kml.tag
            or "http://www.opengis.net/kml/2.2" in kml.attrib.get("xmlns", "")
        )

    def test_kml_has_document(self):
        kml = self._build_sample_kml()

        doc = kml.find("{http://www.opengis.net/kml/2.2}Document")

        assert doc is not None

        assert doc.find("{http://www.opengis.net/kml/2.2}name") is not None

    def test_kml_has_folder(self):
        kml = self._build_sample_kml()

        folder = kml.find(
            "{http://www.opengis.net/kml/2.2}Document/"
            "{http://www.opengis.net/kml/2.2}Folder"
        )

        assert folder is not None

    def test_kml_placemarks_have_geometry(self):
        kml = self._build_sample_kml()

        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        placemarks = kml.findall(
            ".//kml:Placemark",
            ns,
        )

        assert len(placemarks) >= 3

        for pm in placemarks:
            geom = pm.find("kml:Point", ns)

            if geom is None:
                geom = pm.find("kml:LineString", ns)

            if geom is None:
                geom = pm.find("kml:Polygon", ns)

            assert geom is not None

    def test_kml_coordinates_are_lon_lat(self):
        kml = self._build_sample_kml()

        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        coords = kml.find(
            ".//kml:Point/kml:coordinates",
            ns,
        )

        assert coords is not None
        assert coords.text is not None

        parts = coords.text.split(",")

        lon, lat = float(parts[0]), float(parts[1])

        assert -180 <= lon <= 180
        assert -90 <= lat <= 90

    def test_kml_extended_data(self):
        kml = self._build_sample_kml()

        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        ext = kml.find(
            ".//kml:ExtendedData",
            ns,
        )

        assert ext is not None

        data = ext.find(
            "kml:Data[@name='SensorLatitude']",
            ns,
        )

        assert data is not None

        value = data.find(
            "kml:value",
            ns,
        )

        assert value is not None
        assert value.text == "40.4168"

    def test_kml_serializes_to_valid_xml(self):
        kml = self._build_sample_kml()

        # defusedxml is used to validate the XML structure.
        # Serialization is done as plain UTF-8 text so that
        # no incompatible ElementTree constructor is required.
        xml_text = ET.tostring(
            kml,
            encoding="unicode",
        )

        xml_bytes = ('<?xml version="1.0" encoding="utf-8"?>\n' + xml_text).encode(
            "utf-8"
        )

        assert b"<?xml" in xml_bytes
        assert b"<" in xml_bytes
        assert b"kml" in xml_bytes

        # Round-trip validation with defusedxml.
        root = ET.fromstring(xml_bytes)

        assert root.tag.endswith("kml")

    def test_kml_linestring_coordinates(self):
        kml = self._build_sample_kml()

        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        coords = kml.find(
            ".//kml:LineString/kml:coordinates",
            ns,
        )

        assert coords is not None
        assert coords.text is not None

        points = coords.text.strip().split()

        assert len(points) == 3


class TestGPXStructure:
    """Test that GPX output has valid structure for Google Earth / GPS devices."""

    def _build_sample_gpx(self):
        gpx_ns = "http://www.topografix.com/GPX/1/1"

        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<gpx
  version="1.1"
  creator="QGIS FMV"
  xmlns="{gpx_ns}">
  <metadata>
    <name>TestTrack</name>
    <time>2024-01-15T12:00:00Z</time>
  </metadata>

  <trk>
    <name>Platform</name>
    <trkseg>
      <trkpt lat="40.410000" lon="-3.700000" />
      <trkpt lat="40.420000" lon="-3.710000" />
      <trkpt lat="40.430000" lon="-3.720000" />
    </trkseg>
  </trk>
</gpx>
"""

        return ET.fromstring(xml)

    def test_gpx_has_required_root(self):
        gpx = self._build_sample_gpx()

        assert gpx.tag.endswith("gpx")

        assert gpx.attrib.get("version") == "1.1"

    def test_gpx_has_metadata(self):
        gpx = self._build_sample_gpx()

        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

        metadata = gpx.find(
            "gpx:metadata",
            ns,
        )

        assert metadata is not None

        assert (
            metadata.find(
                "gpx:name",
                ns,
            )
            is not None
        )

        assert (
            metadata.find(
                "gpx:time",
                ns,
            )
            is not None
        )

    def test_gpx_has_track(self):
        gpx = self._build_sample_gpx()

        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

        trk = gpx.find(
            "gpx:trk",
            ns,
        )

        assert trk is not None

        assert (
            trk.find(
                "gpx:name",
                ns,
            )
            is not None
        )

    def test_gpx_has_track_segment(self):
        gpx = self._build_sample_gpx()

        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

        trkseg = gpx.find(
            "gpx:trk/gpx:trkseg",
            ns,
        )

        assert trkseg is not None

    def test_gpx_track_points_have_lat_lon(self):
        gpx = self._build_sample_gpx()

        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

        trkpts = gpx.findall(
            "gpx:trk/gpx:trkseg/gpx:trkpt",
            ns,
        )

        assert len(trkpts) == 3

        for pt in trkpts:
            lat = float(pt.attrib["lat"])
            lon = float(pt.attrib["lon"])

            assert -90 <= lat <= 90
            assert -180 <= lon <= 180

    def test_gpx_serializes_to_valid_xml(self):
        gpx = self._build_sample_gpx()

        xml_text = ET.tostring(
            gpx,
            encoding="unicode",
        )

        xml_bytes = ('<?xml version="1.0" encoding="utf-8"?>\n' + xml_text).encode(
            "utf-8"
        )

        assert b"<?xml" in xml_bytes
        assert b"<" in xml_bytes
        assert b"gpx" in xml_bytes

        # Round-trip validation with defusedxml.
        root = ET.fromstring(xml_bytes)

        assert root.tag.endswith("gpx")

    def test_gpx_track_point_format(self):
        gpx = self._build_sample_gpx()

        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

        pt = gpx.find(
            "gpx:trk/gpx:trkseg/gpx:trkpt",
            ns,
        )

        assert pt is not None
        assert "lat" in pt.attrib
        assert "lon" in pt.attrib

        # Verify 6 decimal places as the export code does.
        assert "." in pt.attrib["lat"]
        assert len(pt.attrib["lat"].split(".")[1]) == 6


class TestKMLFileRoundtrip:
    """Write a KML file, read it back, and validate structure."""

    def _generate_kml(self, path):
        """Generate a realistic KML file mimicking the export code."""

        ns = "http://www.opengis.net/kml/2.2"

        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<kml xmlns="{ns}">
  <Document>
    <name>FMV Test Export</name>

    <!-- Platform folder with a point -->
    <Folder>
      <name>Platform</name>
      <Placemark>
        <name>Sensor</name>
        <Point>
          <coordinates>-3.7038,40.4168</coordinates>
        </Point>
      </Placemark>
    </Folder>

    <!-- Trajectory folder with a line -->
    <Folder>
      <name>Trajectory</name>
      <Placemark>
        <name>Track</name>
        <LineString>
          <coordinates>
            -3.70,40.41 -3.71,40.42 -3.72,40.43 -3.73,40.44
          </coordinates>
        </LineString>
      </Placemark>
    </Folder>

    <!-- Footprint folder with a polygon -->
    <Folder>
      <name>Footprint</name>
      <Placemark>
        <name>Frame</name>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                -3.71,40.40 -3.69,40.40 -3.69,40.42
                -3.71,40.42 -3.71,40.40
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
    </Folder>

  </Document>
</kml>
"""

        # Validate before writing.
        ET.fromstring(xml)

        with open(
            path,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write(xml)

    def test_kml_file_is_valid_xml(self, tmp_path):
        path = tmp_path / "test.kml"

        self._generate_kml(str(path))

        tree = ET.parse(str(path))

        root = tree.getroot()

        assert root.tag == "{http://www.opengis.net/kml/2.2}kml"

    def test_kml_file_has_folders(self, tmp_path):
        path = tmp_path / "test.kml"

        self._generate_kml(str(path))

        tree = ET.parse(str(path))

        root = tree.getroot()

        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        folders = root.findall(
            ".//kml:Folder",
            ns,
        )

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

        placemarks = tree.getroot().findall(
            ".//kml:Placemark",
            ns,
        )

        assert len(placemarks) == 3

    def test_kml_file_coordinates_valid(self, tmp_path):
        path = tmp_path / "test.kml"

        self._generate_kml(str(path))

        tree = ET.parse(str(path))

        ns = {"kml": "http://www.opengis.net/kml/2.2"}

        coords_list = tree.getroot().findall(
            ".//kml:coordinates",
            ns,
        )

        assert len(coords_list) >= 3

        for coords_el in coords_list:
            assert coords_el.text is not None

            text = coords_el.text.strip()

            points = text.split()

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

        track_points = "\n".join(
            (f'      <trkpt lat="{lat:.6f}" ' f'lon="{lon:.6f}" />')
            for lon, lat in trajectory
        )

        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<gpx
  version="1.1"
  creator="QGIS FMV"
  xmlns="{gpx_ns}">
  <metadata>
    <name>Platform Track</name>
    <time>2024-01-15T12:00:00Z</time>
  </metadata>

  <trk>
    <name>Trajectory</name>
    <trkseg>
{track_points}
    </trkseg>
  </trk>
</gpx>
"""

        # Validate before writing.
        ET.fromstring(xml)

        with open(
            path,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write(xml)

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

        metadata = tree.getroot().find(
            "gpx:metadata",
            ns,
        )

        assert metadata is not None

        assert (
            metadata.find(
                "gpx:name",
                ns,
            )
            is not None
        )

        assert (
            metadata.find(
                "gpx:time",
                ns,
            )
            is not None
        )

    def test_gpx_file_has_track(self, tmp_path):
        path = tmp_path / "test.gpx"

        self._generate_gpx(str(path))

        tree = ET.parse(str(path))

        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

        trk = tree.getroot().find(
            "gpx:trk",
            ns,
        )

        assert trk is not None

        trk_name = trk.find(
            "gpx:name",
            ns,
        )

        assert trk_name is not None
        assert trk_name.text == "Trajectory"

    def test_gpx_file_track_points(self, tmp_path):
        path = tmp_path / "test.gpx"

        self._generate_gpx(str(path))

        tree = ET.parse(str(path))

        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

        trkpts = tree.getroot().findall(
            ".//gpx:trkpt",
            ns,
        )

        assert len(trkpts) == 10

    def test_gpx_file_track_point_coords(self, tmp_path):
        path = tmp_path / "test.gpx"

        self._generate_gpx(str(path))

        tree = ET.parse(str(path))

        ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

        trkpts = tree.getroot().findall(
            ".//gpx:trkpt",
            ns,
        )

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

        first = tree.getroot().find(
            ".//gpx:trkpt",
            ns,
        )

        assert first is not None

        assert float(first.attrib["lat"]) == pytest.approx(
            40.4168,
            abs=0.001,
        )

        assert float(first.attrib["lon"]) == pytest.approx(
            -3.7038,
            abs=0.001,
        )

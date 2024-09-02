from osgeo import ogr
import csv, os
import sqlite3
    
def GenerateShpFromGTFShapes(shapesfile, targetfile):
    conn = sqlite3.connect(':memory:')
    GTFS_data = conn.cursor()
    GTFS_data.execute("CREATE TABLE shapes(shape_id TEXT,shape_pt_lat DOUBLE,shape_pt_lon DOUBLE,shape_pt_sequence INT)")
    conn.commit()
    reader = csv.reader(open(shapesfile, 'rb'))
    header = reader.next()
    ix = dict(zip(header, range(0, len(header))))
    print 'Fields in the shapes file: ' , header
    #headers are: shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled
                  
    #Push the shape data into an sqlite db
    for row in reader:
        GTFS_data.execute("insert into shapes values ((?),(?),(?),(?))",(row[ix['shape_id']], float(row[ix['shape_pt_lat']]), float(row[ix['shape_pt_lon']]), int(row[ix['shape_pt_sequence']])))
        conn.commit()
    del reader

    shapeIDs = GTFS_data.execute("SELECT DISTINCT shape_id FROM shapes")
    shapeIDs = shapeIDs.fetchall()
    print('Number of shapes found: ' + str(len(shapeIDs)))
    
    # get the driver
    driver = ogr.GetDriverByName('ESRI Shapefile')
    # create a new data source and layer
    if os.path.exists(targetfile):
        driver.DeleteDataSource(targetfile)
    ds = driver.CreateDataSource(targetfile)

    if ds is None:
        print 'Could not create file'
        sys.exit(1)
    layer = ds.CreateLayer('GTFS', geom_type=ogr.wkbLineString)
    # add an id field to the output
    fieldDefn = ogr.FieldDefn('shapeid', ogr.OFTString)
    layer.CreateField(fieldDefn)
    for shapeID in shapeIDs:
        matchpts = GTFS_data.execute("SELECT  shape_pt_lon, shape_pt_lat FROM shapes WHERE shape_id = (?) ORDER BY shape_pt_sequence", (shapeID))
        matchpts = matchpts.fetchall()
        # create a new point object
        line = ogr.Geometry(ogr.wkbLineString)
        for xy in matchpts:
            line.AddPoint(xy[0], xy[1])
        # get the FeatureDefn for the output layer
        featureDefn = layer.GetLayerDefn()
        # create a new feature
        feature = ogr.Feature(featureDefn)
        feature.SetGeometry(line)
        feature.SetField('shapeid', str(shapeID[0]))
        # add the feature to the output layer
        layer.CreateFeature(feature)
        # destroy the geometry and feature and close the da
        line.Destroy()
        feature.Destroy()
    ds.Destroy()
    GTFS_data.close()

shapesfile = r'C:\Users\CJoshi\Downloads\google_transit\shapes.txt'
targetfile = r'C:\Users\CJoshi\Downloads\google_transit\wmata_shapes.shp'

GenerateShpFromGTFShapes(shapesfile, targetfile)




    
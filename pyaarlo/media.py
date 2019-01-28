
import time
import threading
from datetime import datetime
from datetime import timedelta
from pyaarlo.constant import ( LIBRARY_URL,
                                PRELOAD_DAYS )
from pyaarlo.util import ( arlotime_strftime,
                            arlotime_to_datetime,
                            http_stream,
                            http_get )

class ArloMediaLibrary(object):
    """Arlo Library Media module implementation."""

    def __init__( self,arlo ):
        self._arlo      = arlo
        self._lock      = threading.Lock()
        self._load_cbs_ = []
        self._count     = 0
        self._videos    = []

    def __repr__(self):
        return "<{0}:{1}>".format( self.__class__.__name__,self._arlo.name )

    def load( self,days=PRELOAD_DAYS,only_cameras=None,date_from=None,date_to=None,limit=None ):

        self._arlo.info( '(re)loading image library' )

        if not (date_from and date_to):
            now = datetime.today()
            date_from = (now - timedelta(days=days)).strftime('%Y%m%d')
            date_to = now.strftime('%Y%m%d')

        data = self._arlo._be.post( LIBRARY_URL,{ 'dateFrom':date_from,'dateTo':date_to } )
        videos = []
        for video in data:

            camera = self._arlo.lookup_camera_by_id( video.get('deviceId') )
            if not camera:
                continue

            videos.append(ArloVideo(video, camera, self._arlo))

        cbs = []
        with self._lock:
            self._count += 1
            if limit:
                self._videos = videos[:limit]
            else:
                self._videos = videos
            self._arlo.debug( 'ml:count=' + str(self._count) )
            cbs = self._load_cbs_
            self._load_cbs_ = []

        # callback waiting!
        for cb in cbs:
            cb()

    @property
    def videos( self ):
        with self._lock:
            return ( self._count,self._videos )

    @property
    def count( self ):
        with self._lock:
            return self._count

    def videos_for( self,camera ):
        camera_videos = []
        with self._lock:
            for video in self._videos:
                if camera.device_id == video.camera.device_id:
                    camera_videos.append( video )
            return ( self._count,camera_videos )

    def queue_load( self,cb ):
        with self._lock:
            if not self._load_cbs_:
                self._arlo.info( 'queueing (re)loading image library' )
                self._arlo._bg.run_low_in( self.load,2 )
            self._load_cbs_.append( cb )

class ArloVideo(object):
    """Object for Arlo Video file."""

    def __init__( self,attrs,camera,arlo ):
        self._arlo = arlo
        self._attrs = attrs
        self._camera = camera

    def __repr__(self):
        """Representation string of object."""
        return "<{0}:{1}>".format( self.__class__.__name__,self.name )

    @property
    def name(self):
        return "{0}:{1}".format( self._camera.device_id,arlotime_strftime(self.created_at) )

    # pylint: disable=invalid-name
    @property
    def id(self):
        return self._attrs.get('name',None)

    @property
    def created_at(self):
        return self._attrs.get('localCreatedDate',None)

    def created_at_pretty( self, date_format=None ):
        if date_format:
            return arlotime_strftime(self.created_at, date_format=date_format)
        return arlotime_strftime(self.created_at)

    @property
    def created_today(self):
        return self.datetime.date() == datetime.today().date()

    @property
    def datetime(self):
        return arlotime_to_datetime(self.created_at)

    @property
    def content_type(self):
        return self._attrs.get('contentType',None)

    @property
    def camera(self):
        return self._camera

    @property
    def media_duration_seconds(self):
        return self._attrs.get('mediaDurationSecond',None)

    @property
    def triggered_by(self):
        return self._attrs.get('reason',None)

    @property
    def thumbnail_url(self):
        return self._attrs.get('presignedThumbnailUrl',None)

    @property
    def video_url(self):
        return self._attrs.get('presignedContentUrl',None )

    def download_thumbnail( self,filename=None ):
        return http_get( self.thumbnail_url,filename )

    def download_video( self,filename=None ):
        return http_get( self.video_url,filename )

    @property
    def stream_video(self):
        return http_stream( self.video_url )

# vim:sw=4:ts=4:et:
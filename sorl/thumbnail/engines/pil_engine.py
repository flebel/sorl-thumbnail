from cStringIO import StringIO
from sorl.thumbnail.engines.base import EngineBase

try:
    from PIL import Image, ImageFile, ImageDraw
except ImportError:
    import Image, ImageFile, ImageDraw


class Engine(EngineBase):
    def get_image(self, source):
        buf = StringIO(source.read())
        return Image.open(buf)

    def get_image_size(self, image):
        return image.size

    def is_valid_image(self, raw_data):
        buf = StringIO(raw_data)
        try:
            trial_image = Image.open(buf)
            trial_image.verify()
        except Exception:
            return False
        return True

    def _orientation(self, image):
        try:
            exif = image._getexif()
        except AttributeError:
            exif = None
        if exif:
            orientation = exif.get(0x0112)
            if orientation == 2:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 3:
                image = image.rotate(180)
            elif orientation == 4:
                image = image.transpose(Image.FLIP_TOP_BOTTOM)
            elif orientation == 5:
                image = image.rotate(-90).transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 6:
                image = image.rotate(-90)
            elif orientation == 7:
                image = image.rotate(90).transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 8:
                image = image.rotate(90)
        return image

    def _colorspace(self, image, colorspace):
        if colorspace == 'RGB':
            if image.mode == 'RGBA':
                return image # RGBA is just RGB + Alpha
            if image.mode == 'P' and 'transparency' in image.info:
                return image.convert('RGBA')
            return image.convert('RGB')
        if colorspace == 'GRAY':
            return image.convert('L')
        return image

    def _scale(self, image, width, height):
        return image.resize((width, height), resample=Image.ANTIALIAS)

    def _crop(self, image, width, height, x_offset, y_offset):
        return image.crop((x_offset, y_offset,
                           width + x_offset, height + y_offset))

    def _get_raw_data(self, image, format_, quality, progressive=False):
        buf = StringIO()
        params = {
            'format': format_,
            'quality': quality,
            'optimize': 1,
        }
        if format_ == 'JPEG' and progressive:
            params['progressive'] = True
        # PIL can have problems saving large JPEGs if MAXBLOCK isn't big enough,
        # So if we have a problem saving, we temporarily increase it.
        # Snipped borrowed from
        # https://github.com/matthewwithanm/pilkit/blob/master/pilkit/utils.py#L205
        # https://github.com/python-imaging/Pillow/issues/148
        # MAXBLOCK must be at least as big as...
        new_maxblock = max(
            # (len(options['exif']) if 'exif' in options else 0) + 5,  # ...the entire exif header block
            image.size[0] * 4,  # ...a complete scan line
            3 * image.size[0] * image.size[1],  # ...3 bytes per every pixel in the image
        )
        if new_maxblock < ImageFile.MAXBLOCK:
            raise
        old_maxblock = ImageFile.MAXBLOCK
        ImageFile.MAXBLOCK = new_maxblock
        try:
            image.save(buf, **params)
        except IOError:
            params.pop('optimize')
            image.save(buf, **params)
        finally:
            ImageFile.MAXBLOCK = old_maxblock
        raw_data = buf.getvalue()
        buf.close()
        return raw_data


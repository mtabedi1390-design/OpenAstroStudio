"""
libraries/astropy_adapters.py
-------------------------------
گاهی عملیات موردنیاز یک property است نه یک تابع مستقل (مثل coord.galactic)،
یا امضای تابع اصلی برای بلوک‌سازی مناسب نیست. طبق طرح اصلی، "Plugin System"
دقیقاً همین‌جا وارد می‌شود: به‌جای دست‌کاری کتابخانه‌ی اصلی، یک تابع adapter
نازک می‌نویسیم که Reflection Engine می‌تواند آن را مثل هر تابع دیگری بخواند.
"""

from astropy.coordinates import SkyCoord


def to_galactic(coord: SkyCoord) -> SkyCoord:
    """مختصات ورودی را به سیستم مختصات کهکشانی (Galactic) تبدیل می‌کند.

    Parameters
    ----------
    coord : SkyCoord
        شیء مختصات ورودی (در هر فریمی، مثلاً ICRS).

    Returns
    -------
    SkyCoord
        همان مختصات، تبدیل‌شده به فریم Galactic.
    """
    return coord.galactic


def separation_deg(coord1: SkyCoord, coord2: SkyCoord) -> float:
    """فاصله‌ی زاویه‌ای بین دو مختصات آسمانی را بر حسب درجه برمی‌گرداند.

    Parameters
    ----------
    coord1 : SkyCoord
        مختصات اول.
    coord2 : SkyCoord
        مختصات دوم.

    Returns
    -------
    float
        فاصله‌ی زاویه‌ای بر حسب درجه.
    """
    return coord1.separation(coord2).degree

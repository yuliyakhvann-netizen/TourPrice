class TourPriceError(Exception):
    pass


class OperatorLoginError(TourPriceError):
    pass


class OperatorSearchError(TourPriceError):
    pass


class SessionExpiredError(TourPriceError):
    pass


class NormalizationError(TourPriceError):
    pass


class NotFoundError(TourPriceError):
    pass

from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from typing import ClassVar as _ClassVar

DESCRIPTOR: _descriptor.FileDescriptor

class EPublishedFileQueryType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_PublishedFileQueryType_RankedByVote: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByPublicationDate: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_AcceptedForGameRankedByAcceptanceDate: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByTrend: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_FavoritedByFriendsRankedByPublicationDate: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_CreatedByFriendsRankedByPublicationDate: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByNumTimesReported: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_CreatedByFollowedUsersRankedByPublicationDate: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_NotYetRated: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByTotalUniqueSubscriptions: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByTotalVotesAsc: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByVotesUp: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByTextSearch: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByPlaytimeTrend: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByTotalPlaytime: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByAveragePlaytimeTrend: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByLifetimeAveragePlaytime: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByPlaytimeSessionsTrend: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByLifetimePlaytimeSessions: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByInappropriateContentRating: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByBanContentCheck: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByLastUpdatedDate: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByNumParentItems: _ClassVar[EPublishedFileQueryType]
    k_PublishedFileQueryType_RankedByNumParentCollections: _ClassVar[EPublishedFileQueryType]

class EPublishedFileInappropriateProvider(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EPublishedFileInappropriateProvider_Invalid: _ClassVar[EPublishedFileInappropriateProvider]
    k_EPublishedFileInappropriateProvider_Google: _ClassVar[EPublishedFileInappropriateProvider]
    k_EPublishedFileInappropriateProvider_Amazon: _ClassVar[EPublishedFileInappropriateProvider]

class EPublishedFileInappropriateResult(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EPublishedFileInappropriateResult_NotScanned: _ClassVar[EPublishedFileInappropriateResult]
    k_EPublishedFileInappropriateResult_VeryUnlikely: _ClassVar[EPublishedFileInappropriateResult]
    k_EPublishedFileInappropriateResult_Unlikely: _ClassVar[EPublishedFileInappropriateResult]
    k_EPublishedFileInappropriateResult_Possible: _ClassVar[EPublishedFileInappropriateResult]
    k_EPublishedFileInappropriateResult_Likely: _ClassVar[EPublishedFileInappropriateResult]
    k_EPublishedFileInappropriateResult_VeryLikely: _ClassVar[EPublishedFileInappropriateResult]

class EPersonaStateFlag(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EPersonaStateFlag_HasRichPresence: _ClassVar[EPersonaStateFlag]
    k_EPersonaStateFlag_InJoinableGame: _ClassVar[EPersonaStateFlag]
    k_EPersonaStateFlag_Golden: _ClassVar[EPersonaStateFlag]
    k_EPersonaStateFlag_RemotePlayTogether: _ClassVar[EPersonaStateFlag]
    k_EPersonaStateFlag_ClientTypeWeb: _ClassVar[EPersonaStateFlag]
    k_EPersonaStateFlag_ClientTypeMobile: _ClassVar[EPersonaStateFlag]
    k_EPersonaStateFlag_ClientTypeTenfoot: _ClassVar[EPersonaStateFlag]
    k_EPersonaStateFlag_ClientTypeVR: _ClassVar[EPersonaStateFlag]
    k_EPersonaStateFlag_LaunchTypeGamepad: _ClassVar[EPersonaStateFlag]
    k_EPersonaStateFlag_LaunchTypeCompatTool: _ClassVar[EPersonaStateFlag]

class EContentCheckProvider(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EContentCheckProvider_Invalid: _ClassVar[EContentCheckProvider]
    k_EContentCheckProvider_Google_DEPRECATED: _ClassVar[EContentCheckProvider]
    k_EContentCheckProvider_Amazon: _ClassVar[EContentCheckProvider]
    k_EContentCheckProvider_Local: _ClassVar[EContentCheckProvider]
    k_EContentCheckProvider_GoogleVertexAI: _ClassVar[EContentCheckProvider]
    k_EContentCheckProvider_GoogleGemini: _ClassVar[EContentCheckProvider]
    k_EContentCheckProvider_SteamLearn: _ClassVar[EContentCheckProvider]

class EProfileCustomizationType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EProfileCustomizationTypeInvalid: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeRareAchievementShowcase: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeGameCollector: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeItemShowcase: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeTradeShowcase: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeBadges: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeFavoriteGame: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeScreenshotShowcase: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeCustomText: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeFavoriteGroup: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeRecommendation: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeWorkshopItem: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeMyWorkshop: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeArtworkShowcase: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeVideoShowcase: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeGuides: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeMyGuides: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeAchievements: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeGreenlight: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeMyGreenlight: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeSalien: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeLoyaltyRewardReactions: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeSingleArtworkShowcase: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeAchievementsCompletionist: _ClassVar[EProfileCustomizationType]
    k_EProfileCustomizationTypeReplay: _ClassVar[EProfileCustomizationType]

class EPublishedFileStorageSystem(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EPublishedFileStorageSystemInvalid: _ClassVar[EPublishedFileStorageSystem]
    k_EPublishedFileStorageSystemLegacyCloud: _ClassVar[EPublishedFileStorageSystem]
    k_EPublishedFileStorageSystemDepot: _ClassVar[EPublishedFileStorageSystem]
    k_EPublishedFileStorageSystemUGCCloud: _ClassVar[EPublishedFileStorageSystem]

class ECloudStoragePersistState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ECloudStoragePersistStatePersisted: _ClassVar[ECloudStoragePersistState]
    k_ECloudStoragePersistStateForgotten: _ClassVar[ECloudStoragePersistState]
    k_ECloudStoragePersistStateDeleted: _ClassVar[ECloudStoragePersistState]

class ESDCardFormatStage(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESDCardFormatStage_Invalid: _ClassVar[ESDCardFormatStage]
    k_ESDCardFormatStage_Starting: _ClassVar[ESDCardFormatStage]
    k_ESDCardFormatStage_Testing: _ClassVar[ESDCardFormatStage]
    k_ESDCardFormatStage_Rescuing: _ClassVar[ESDCardFormatStage]
    k_ESDCardFormatStage_Formatting: _ClassVar[ESDCardFormatStage]
    k_ESDCardFormatStage_Finalizing: _ClassVar[ESDCardFormatStage]

class EStorageFormatStage(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EStorageFormatStage_Invalid: _ClassVar[EStorageFormatStage]
    k_EStorageFormatStage_NotRunning: _ClassVar[EStorageFormatStage]
    k_EStorageFormatStage_Starting: _ClassVar[EStorageFormatStage]
    k_EStorageFormatStage_Testing: _ClassVar[EStorageFormatStage]
    k_EStorageFormatStage_Rescuing: _ClassVar[EStorageFormatStage]
    k_EStorageFormatStage_Formatting: _ClassVar[EStorageFormatStage]
    k_EStorageFormatStage_Finalizing: _ClassVar[EStorageFormatStage]

class ESystemFanControlMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_SystemFanControlMode_Invalid: _ClassVar[ESystemFanControlMode]
    k_SystemFanControlMode_Disabled: _ClassVar[ESystemFanControlMode]
    k_SystemFanControlMode_Default: _ClassVar[ESystemFanControlMode]

class EColorGamutLabelSet(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ColorGamutLabelSet_Default: _ClassVar[EColorGamutLabelSet]
    k_ColorGamutLabelSet_sRGB_Native: _ClassVar[EColorGamutLabelSet]
    k_ColorGamutLabelSet_Native_sRGB_Boosted: _ClassVar[EColorGamutLabelSet]

class EWindowStackingOrder(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EWindowStackingOrder_Invalid: _ClassVar[EWindowStackingOrder]
    k_EWindowStackingOrder_Top: _ClassVar[EWindowStackingOrder]
    k_EWindowStackingOrder_Bottom: _ClassVar[EWindowStackingOrder]

class EBluetoothDeviceType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_BluetoothDeviceType_Invalid: _ClassVar[EBluetoothDeviceType]
    k_BluetoothDeviceType_Unknown: _ClassVar[EBluetoothDeviceType]
    k_BluetoothDeviceType_Phone: _ClassVar[EBluetoothDeviceType]
    k_BluetoothDeviceType_Computer: _ClassVar[EBluetoothDeviceType]
    k_BluetoothDeviceType_Headset: _ClassVar[EBluetoothDeviceType]
    k_BluetoothDeviceType_Headphones: _ClassVar[EBluetoothDeviceType]
    k_BluetoothDeviceType_Speakers: _ClassVar[EBluetoothDeviceType]
    k_BluetoothDeviceType_OtherAudio: _ClassVar[EBluetoothDeviceType]
    k_BluetoothDeviceType_Mouse: _ClassVar[EBluetoothDeviceType]
    k_BluetoothDeviceType_Joystick: _ClassVar[EBluetoothDeviceType]
    k_BluetoothDeviceType_Gamepad: _ClassVar[EBluetoothDeviceType]
    k_BluetoothDeviceType_Keyboard: _ClassVar[EBluetoothDeviceType]

class ESpeakerConfiguration(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESpeakerConfiguration_Other: _ClassVar[ESpeakerConfiguration]
    k_ESpeakerConfiguration_Stereo: _ClassVar[ESpeakerConfiguration]
    k_ESpeakerConfiguration_51: _ClassVar[ESpeakerConfiguration]
    k_ESpeakerConfiguration_71: _ClassVar[ESpeakerConfiguration]
    k_ESpeakerConfiguration_51_Ac3: _ClassVar[ESpeakerConfiguration]

class ESystemAudioDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_SystemAudioDirection_Invalid: _ClassVar[ESystemAudioDirection]
    k_SystemAudioDirection_Input: _ClassVar[ESystemAudioDirection]
    k_SystemAudioDirection_Output: _ClassVar[ESystemAudioDirection]

class ESystemAudioChannel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_SystemAudioChannel_Invalid: _ClassVar[ESystemAudioChannel]
    k_SystemAudioChannel_Aggregated: _ClassVar[ESystemAudioChannel]
    k_SystemAudioChannel_FrontLeft: _ClassVar[ESystemAudioChannel]
    k_SystemAudioChannel_FrontRight: _ClassVar[ESystemAudioChannel]
    k_SystemAudioChannel_LFE: _ClassVar[ESystemAudioChannel]
    k_SystemAudioChannel_BackLeft: _ClassVar[ESystemAudioChannel]
    k_SystemAudioChannel_BackRight: _ClassVar[ESystemAudioChannel]
    k_SystemAudioChannel_FrontCenter: _ClassVar[ESystemAudioChannel]
    k_SystemAudioChannel_Unknown: _ClassVar[ESystemAudioChannel]
    k_SystemAudioChannel_Mono: _ClassVar[ESystemAudioChannel]

class ESystemAudioPortType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_SystemAudioPortType_Invalid: _ClassVar[ESystemAudioPortType]
    k_SystemAudioPortType_Unknown: _ClassVar[ESystemAudioPortType]
    k_SystemAudioPortType_Audio32f: _ClassVar[ESystemAudioPortType]
    k_SystemAudioPortType_Midi8b: _ClassVar[ESystemAudioPortType]
    k_SystemAudioPortType_Video32RGBA: _ClassVar[ESystemAudioPortType]

class ESystemAudioPortDirection(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_SystemAudioPortDirection_Invalid: _ClassVar[ESystemAudioPortDirection]
    k_SystemAudioPortDirection_Input: _ClassVar[ESystemAudioPortDirection]
    k_SystemAudioPortDirection_Output: _ClassVar[ESystemAudioPortDirection]

class ESystemServiceState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESystemServiceState_Unavailable: _ClassVar[ESystemServiceState]
    k_ESystemServiceState_Disabled: _ClassVar[ESystemServiceState]
    k_ESystemServiceState_Enabled: _ClassVar[ESystemServiceState]

class EBluetoothAudioPreference(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EBluetoothAudioPreference_Quality: _ClassVar[EBluetoothAudioPreference]
    k_EBluetoothAudioPreference_Latency: _ClassVar[EBluetoothAudioPreference]

class EGraphicsPerfOverlayLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EGraphicsPerfOverlayLevel_Hidden: _ClassVar[EGraphicsPerfOverlayLevel]
    k_EGraphicsPerfOverlayLevel_Basic: _ClassVar[EGraphicsPerfOverlayLevel]
    k_EGraphicsPerfOverlayLevel_Medium: _ClassVar[EGraphicsPerfOverlayLevel]
    k_EGraphicsPerfOverlayLevel_Full: _ClassVar[EGraphicsPerfOverlayLevel]
    k_EGraphicsPerfOverlayLevel_Minimal: _ClassVar[EGraphicsPerfOverlayLevel]

class EGPUPerformanceLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EGPUPerformanceLevel_Invalid: _ClassVar[EGPUPerformanceLevel]
    k_EGPUPerformanceLevel_Auto: _ClassVar[EGPUPerformanceLevel]
    k_EGPUPerformanceLevel_Manual: _ClassVar[EGPUPerformanceLevel]
    k_EGPUPerformanceLevel_Low: _ClassVar[EGPUPerformanceLevel]
    k_EGPUPerformanceLevel_High: _ClassVar[EGPUPerformanceLevel]
    k_EGPUPerformanceLevel_Profiling: _ClassVar[EGPUPerformanceLevel]

class ESplitScalingFilter(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESplitScalingFilter_Invalid: _ClassVar[ESplitScalingFilter]
    k_ESplitScalingFilter_Linear: _ClassVar[ESplitScalingFilter]
    k_ESplitScalingFilter_Nearest: _ClassVar[ESplitScalingFilter]
    k_ESplitScalingFilter_Sharp: _ClassVar[ESplitScalingFilter]
    k_ESplitScalingFilter_NIS_Deprecated: _ClassVar[ESplitScalingFilter]

class ESplitScalingScaler(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESplitScalingScaler_Invalid: _ClassVar[ESplitScalingScaler]
    k_ESplitScalingScaler_Auto: _ClassVar[ESplitScalingScaler]
    k_ESplitScalingScaler_Integer: _ClassVar[ESplitScalingScaler]
    k_ESplitScalingScaler_Fit: _ClassVar[ESplitScalingScaler]
    k_ESplitScalingScaler_Fill: _ClassVar[ESplitScalingScaler]
    k_ESplitScalingScaler_Stretch: _ClassVar[ESplitScalingScaler]

class EGamescopeBlurMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EGamescopeBlurMode_Disabled: _ClassVar[EGamescopeBlurMode]
    k_EGamescopeBlurMode_IfOccluded: _ClassVar[EGamescopeBlurMode]
    k_EGamescopeBlurMode_Always: _ClassVar[EGamescopeBlurMode]

class ESLSHelper(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESLSHelper_Invalid: _ClassVar[ESLSHelper]
    k_ESLSHelper_Minidump: _ClassVar[ESLSHelper]
    k_ESLSHelper_Kdump: _ClassVar[ESLSHelper]
    k_ESLSHelper_Journal: _ClassVar[ESLSHelper]
    k_ESLSHelper_Gpu: _ClassVar[ESLSHelper]
    k_ESLSHelper_SystemInfo: _ClassVar[ESLSHelper]
    k_ESLSHelper_Devcoredump: _ClassVar[ESLSHelper]

class EHDRVisualization(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EHDRVisualization_None: _ClassVar[EHDRVisualization]
    k_EHDRVisualization_Heatmap: _ClassVar[EHDRVisualization]
    k_EHDRVisualization_Analysis: _ClassVar[EHDRVisualization]
    k_EHDRVisualization_HeatmapExtended: _ClassVar[EHDRVisualization]
    k_EHDRVisualization_HeatmapClassic: _ClassVar[EHDRVisualization]

class EHDRToneMapOperator(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EHDRToneMapOperator_Invalid: _ClassVar[EHDRToneMapOperator]
    k_EHDRToneMapOperator_Uncharted: _ClassVar[EHDRToneMapOperator]
    k_EHDRToneMapOperator_Reinhard: _ClassVar[EHDRToneMapOperator]

class ECPUGovernor(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ECPUGovernor_Invalid: _ClassVar[ECPUGovernor]
    k_ECPUGovernor_Perf: _ClassVar[ECPUGovernor]
    k_ECPUGovernor_Powersave: _ClassVar[ECPUGovernor]
    k_ECPUGovernor_Manual: _ClassVar[ECPUGovernor]

class EUpdaterType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EUpdaterType_Invalid: _ClassVar[EUpdaterType]
    k_EUpdaterType_Client: _ClassVar[EUpdaterType]
    k_EUpdaterType_OS: _ClassVar[EUpdaterType]
    k_EUpdaterType_BIOS: _ClassVar[EUpdaterType]
    k_EUpdaterType_Aggregated: _ClassVar[EUpdaterType]
    k_EUpdaterType_Test1: _ClassVar[EUpdaterType]
    k_EUpdaterType_Test2: _ClassVar[EUpdaterType]
    k_EUpdaterType_Dummy: _ClassVar[EUpdaterType]

class EUpdaterState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EUpdaterState_Invalid: _ClassVar[EUpdaterState]
    k_EUpdaterState_UpToDate: _ClassVar[EUpdaterState]
    k_EUpdaterState_Checking: _ClassVar[EUpdaterState]
    k_EUpdaterState_Available: _ClassVar[EUpdaterState]
    k_EUpdaterState_Applying: _ClassVar[EUpdaterState]
    k_EUpdaterState_ClientRestartPending: _ClassVar[EUpdaterState]
    k_EUpdaterState_SystemRestartPending: _ClassVar[EUpdaterState]
    k_EUpdaterState_RollBack: _ClassVar[EUpdaterState]

class EStorageBlockContentType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EStorageBlockContentType_Invalid: _ClassVar[EStorageBlockContentType]
    k_EStorageBlockContentType_Unknown: _ClassVar[EStorageBlockContentType]
    k_EStorageBlockContentType_FileSystem: _ClassVar[EStorageBlockContentType]
    k_EStorageBlockContentType_Crypto: _ClassVar[EStorageBlockContentType]
    k_EStorageBlockContentType_Raid: _ClassVar[EStorageBlockContentType]

class EStorageBlockFileSystemType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EStorageBlockFileSystemType_Invalid: _ClassVar[EStorageBlockFileSystemType]
    k_EStorageBlockFileSystemType_Unknown: _ClassVar[EStorageBlockFileSystemType]
    k_EStorageBlockFileSystemType_VFat: _ClassVar[EStorageBlockFileSystemType]
    k_EStorageBlockFileSystemType_Ext4: _ClassVar[EStorageBlockFileSystemType]

class EStorageDriveMediaType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EStorageDriveMediaType_Invalid: _ClassVar[EStorageDriveMediaType]
    k_EStorageDriveMediaType_Unknown: _ClassVar[EStorageDriveMediaType]
    k_EStorageDriveMediaType_HDD: _ClassVar[EStorageDriveMediaType]
    k_EStorageDriveMediaType_SSD: _ClassVar[EStorageDriveMediaType]
    k_EStorageDriveMediaType_Removable: _ClassVar[EStorageDriveMediaType]

class ESystemDisplayCompatibilityMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESystemDisplayCompatibilityMode_Invalid: _ClassVar[ESystemDisplayCompatibilityMode]
    k_ESystemDisplayCompatibilityMode_None: _ClassVar[ESystemDisplayCompatibilityMode]
    k_ESystemDisplayCompatibilityMode_MinimalBandwith: _ClassVar[ESystemDisplayCompatibilityMode]

class ESteamOSCompatibilityCategory(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESteamOSCompatibilityCategory_Unknown: _ClassVar[ESteamOSCompatibilityCategory]
    k_ESteamOSCompatibilityCategory_Unsupported: _ClassVar[ESteamOSCompatibilityCategory]
    k_ESteamOSCompatibilityCategory_Compatible: _ClassVar[ESteamOSCompatibilityCategory]

class ESteamOSCompatibilityResultDisplayType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESteamOSCompatibilityResultDisplayType_Invisible: _ClassVar[ESteamOSCompatibilityResultDisplayType]
    k_ESteamOSCompatibilityResultDisplayType_Informational: _ClassVar[ESteamOSCompatibilityResultDisplayType]
    k_ESteamOSCompatibilityResultDisplayType_Unsupported: _ClassVar[ESteamOSCompatibilityResultDisplayType]
    k_ESteamOSCompatibilityResultDisplayType_Compatible: _ClassVar[ESteamOSCompatibilityResultDisplayType]

class ESteamDeckCompatibilityCategory(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESteamDeckCompatibilityCategory_Unknown: _ClassVar[ESteamDeckCompatibilityCategory]
    k_ESteamDeckCompatibilityCategory_Unsupported: _ClassVar[ESteamDeckCompatibilityCategory]
    k_ESteamDeckCompatibilityCategory_Playable: _ClassVar[ESteamDeckCompatibilityCategory]
    k_ESteamDeckCompatibilityCategory_Verified: _ClassVar[ESteamDeckCompatibilityCategory]

class ESteamDeckCompatibilityResultDisplayType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESteamDeckCompatibilityResultDisplayType_Invisible: _ClassVar[ESteamDeckCompatibilityResultDisplayType]
    k_ESteamDeckCompatibilityResultDisplayType_Informational: _ClassVar[ESteamDeckCompatibilityResultDisplayType]
    k_ESteamDeckCompatibilityResultDisplayType_Unsupported: _ClassVar[ESteamDeckCompatibilityResultDisplayType]
    k_ESteamDeckCompatibilityResultDisplayType_Playable: _ClassVar[ESteamDeckCompatibilityResultDisplayType]
    k_ESteamDeckCompatibilityResultDisplayType_Verified: _ClassVar[ESteamDeckCompatibilityResultDisplayType]

class ESteamDeckCompatibilityTestResult(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESteamDeckCompatibilityTestResult_Invalid: _ClassVar[ESteamDeckCompatibilityTestResult]
    k_ESteamDeckCompatibilityTestResult_NotApplicable: _ClassVar[ESteamDeckCompatibilityTestResult]
    k_ESteamDeckCompatibilityTestResult_Pass: _ClassVar[ESteamDeckCompatibilityTestResult]
    k_ESteamDeckCompatibilityTestResult_Fail: _ClassVar[ESteamDeckCompatibilityTestResult]
    k_ESteamDeckCompatibilityTestResult_FailMinor: _ClassVar[ESteamDeckCompatibilityTestResult]

class EACState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EACState_Unknown: _ClassVar[EACState]
    k_EACState_Disconnected: _ClassVar[EACState]
    k_EACState_Connected: _ClassVar[EACState]
    k_EACState_ConnectedSlow: _ClassVar[EACState]

class EBatteryState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EBatteryState_Unknown: _ClassVar[EBatteryState]
    k_EBatteryState_Discharging: _ClassVar[EBatteryState]
    k_EBatteryState_Charging: _ClassVar[EBatteryState]
    k_EBatteryState_Full: _ClassVar[EBatteryState]

class EOSBranch(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EOSBranch_Unknown: _ClassVar[EOSBranch]
    k_EOSBranch_Release: _ClassVar[EOSBranch]
    k_EOSBranch_ReleaseCandidate: _ClassVar[EOSBranch]
    k_EOSBranch_Beta: _ClassVar[EOSBranch]
    k_EOSBranch_BetaCandidate: _ClassVar[EOSBranch]
    k_EOSBranch_Preview: _ClassVar[EOSBranch]
    k_EOSBranch_PreviewCandidate: _ClassVar[EOSBranch]
    k_EOSBranch_Main: _ClassVar[EOSBranch]
    k_EOSBranch_Staging: _ClassVar[EOSBranch]

class EBrowserGPUStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EBrowserGPUStatus_Invalid: _ClassVar[EBrowserGPUStatus]
    k_EBrowserGPUStatus_Enabled: _ClassVar[EBrowserGPUStatus]
    k_EBrowserGPUStatus_DisabledUnknown: _ClassVar[EBrowserGPUStatus]
    k_EBrowserGPUStatus_DisabledCrashCount: _ClassVar[EBrowserGPUStatus]
    k_EBrowserGPUStatus_DisabledBlocklist: _ClassVar[EBrowserGPUStatus]
    k_EBrowserGPUStatus_DisabledJSRequest: _ClassVar[EBrowserGPUStatus]
    k_EBrowserGPUStatus_DisabledCommandLine: _ClassVar[EBrowserGPUStatus]
    k_EBrowserGPUStatus_DisabledRuntimeDetect: _ClassVar[EBrowserGPUStatus]
    k_EBrowserGPUStatus_DisabledChildCommandLine: _ClassVar[EBrowserGPUStatus]
    k_EBrowserGPUStatus_DisabledCompositingCommandLine: _ClassVar[EBrowserGPUStatus]

class EBrowserFeatureStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EBrowserFeatureStatus_Invalid: _ClassVar[EBrowserFeatureStatus]
    k_EBrowserFeatureStatus_NotFound: _ClassVar[EBrowserFeatureStatus]
    k_EBrowserFeatureStatus_Unknown: _ClassVar[EBrowserFeatureStatus]
    k_EBrowserFeatureStatus_DisabledSoftware: _ClassVar[EBrowserFeatureStatus]
    k_EBrowserFeatureStatus_DisabledOff: _ClassVar[EBrowserFeatureStatus]
    k_EBrowserFeatureStatus_DisabledOffOk: _ClassVar[EBrowserFeatureStatus]
    k_EBrowserFeatureStatus_UnavailableSoftware: _ClassVar[EBrowserFeatureStatus]
    k_EBrowserFeatureStatus_UnavailableOff: _ClassVar[EBrowserFeatureStatus]
    k_EBrowserFeatureStatus_UnavailableOffOk: _ClassVar[EBrowserFeatureStatus]
    k_EBrowserFeatureStatus_EnabledReadback: _ClassVar[EBrowserFeatureStatus]
    k_EBrowserFeatureStatus_EnabledForce: _ClassVar[EBrowserFeatureStatus]
    k_EBrowserFeatureStatus_Enabled: _ClassVar[EBrowserFeatureStatus]
    k_EBrowserFeatureStatus_EnabledOn: _ClassVar[EBrowserFeatureStatus]
    k_EBrowserFeatureStatus_EnabledForceOn: _ClassVar[EBrowserFeatureStatus]

class EGpuDriverId(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EGpuDriverId_Invalid: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_Unknown: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_AmdProprietary: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_AmdOpenSource: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_MesaRadv: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_NvidiaProprietary: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_IntelPropietary: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_MesaIntel: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_QualcommProprietary: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_ArmProprietary: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_GoogleSwiftshader: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_BroadcomProprietary: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_MesaLLVMPipe: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_MoltenVK: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_MesaTurnip: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_MesaPanVK: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_MesaVenus: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_MesaDozen: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_MesaNVK: _ClassVar[EGpuDriverId]
    k_EGpuDriverId_MesaHoneyKrisp: _ClassVar[EGpuDriverId]

class ECommunityItemClass(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ECommunityItemClass_Invalid: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_Badge: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_GameCard: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_ProfileBackground: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_Emoticon: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_BoosterPack: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_Consumable: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_GameGoo: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_ProfileModifier: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_Scene: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_SalienItem: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_Sticker: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_ChatEffect: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_MiniProfileBackground: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_AvatarFrame: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_AnimatedAvatar: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_SteamDeckKeyboardSkin: _ClassVar[ECommunityItemClass]
    k_ECommunityItemClass_SteamDeckStartupMovie: _ClassVar[ECommunityItemClass]

class ESteamDeckCompatibilityFeedback(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESteamDeckCompatibilityFeedback_Unset: _ClassVar[ESteamDeckCompatibilityFeedback]
    k_ESteamDeckCompatibilityFeedback_Agree: _ClassVar[ESteamDeckCompatibilityFeedback]
    k_ESteamDeckCompatibilityFeedback_Disagree: _ClassVar[ESteamDeckCompatibilityFeedback]
    k_ESteamDeckCompatibilityFeedback_Ignore: _ClassVar[ESteamDeckCompatibilityFeedback]

class EProvideDeckFeedbackPreference(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EProvideDeckFeedbackPreference_Unset: _ClassVar[EProvideDeckFeedbackPreference]
    k_EProvideDeckFeedbackPreference_Yes: _ClassVar[EProvideDeckFeedbackPreference]
    k_EProvideDeckFeedbackPreference_No: _ClassVar[EProvideDeckFeedbackPreference]

class EHardwareCompatibilityFeedbackDetails(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EHardwareCompatibilityFeedbackDetails_Unset: _ClassVar[EHardwareCompatibilityFeedbackDetails]
    k_EHardwareCompatibilityFeedbackDetails_Performance: _ClassVar[EHardwareCompatibilityFeedbackDetails]
    k_EHardwareCompatibilityFeedbackDetails_Stability: _ClassVar[EHardwareCompatibilityFeedbackDetails]
    k_EHardwareCompatibilityFeedbackDetails_Legibility: _ClassVar[EHardwareCompatibilityFeedbackDetails]
    k_EHardwareCompatibilityFeedbackDetails_Input: _ClassVar[EHardwareCompatibilityFeedbackDetails]
    k_EHardwareCompatibilityFeedbackDetails_Other: _ClassVar[EHardwareCompatibilityFeedbackDetails]

class EGameFrameRateReportingPreference(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EGameFrameRateReportingPreference_Unset: _ClassVar[EGameFrameRateReportingPreference]
    k_EGameFrameRateReportingPreference_No: _ClassVar[EGameFrameRateReportingPreference]
    k_EGameFrameRateReportingPreference_Yes_Anonymous: _ClassVar[EGameFrameRateReportingPreference]
    k_EGameFrameRateReportingPreference_Yes_NonAnonymous: _ClassVar[EGameFrameRateReportingPreference]

class ETouchGesture(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ETouchGestureNone: _ClassVar[ETouchGesture]
    k_ETouchGestureTouch: _ClassVar[ETouchGesture]
    k_ETouchGestureTap: _ClassVar[ETouchGesture]
    k_ETouchGestureDoubleTap: _ClassVar[ETouchGesture]
    k_ETouchGestureShortPress: _ClassVar[ETouchGesture]
    k_ETouchGestureLongPress: _ClassVar[ETouchGesture]
    k_ETouchGestureLongTap: _ClassVar[ETouchGesture]
    k_ETouchGestureTwoFingerTap: _ClassVar[ETouchGesture]
    k_ETouchGestureTapCancelled: _ClassVar[ETouchGesture]
    k_ETouchGesturePinchBegin: _ClassVar[ETouchGesture]
    k_ETouchGesturePinchUpdate: _ClassVar[ETouchGesture]
    k_ETouchGesturePinchEnd: _ClassVar[ETouchGesture]
    k_ETouchGestureFlingStart: _ClassVar[ETouchGesture]
    k_ETouchGestureFlingCancelled: _ClassVar[ETouchGesture]

class ESessionPersistence(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ESessionPersistence_Invalid: _ClassVar[ESessionPersistence]
    k_ESessionPersistence_Ephemeral: _ClassVar[ESessionPersistence]
    k_ESessionPersistence_Persistent: _ClassVar[ESessionPersistence]

class ENewSteamAnnouncementState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ENewSteamAnnouncementState_Invalid: _ClassVar[ENewSteamAnnouncementState]
    k_ENewSteamAnnouncementState_AllRead: _ClassVar[ENewSteamAnnouncementState]
    k_ENewSteamAnnouncementState_NewAnnouncement: _ClassVar[ENewSteamAnnouncementState]
    k_ENewSteamAnnouncementState_FeaturedAnnouncement: _ClassVar[ENewSteamAnnouncementState]

class EForumType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EForumType_Invalid: _ClassVar[EForumType]
    k_EForumType_General: _ClassVar[EForumType]
    k_EForumType_ReportedPosts: _ClassVar[EForumType]
    k_EForumType_Workshop: _ClassVar[EForumType]
    k_EForumType_PublishedFile: _ClassVar[EForumType]
    k_EForumType_Trading: _ClassVar[EForumType]
    k_EForumType_PlayTest: _ClassVar[EForumType]
    k_EForumType_Event: _ClassVar[EForumType]
    k_EForumType_Max: _ClassVar[EForumType]

class ECommentThreadType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ECommentThreadTypeInvalid: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeScreenshot_Deprecated: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeWorkshopAccount_Developer: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeWorkshopAccount_Public: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypePublishedFile_Developer: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypePublishedFile_Public: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeTest: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeForumTopic: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeRecommendation: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeVideo_Deprecated: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeProfile: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeNewsPost: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeClan: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeClanAnnouncement: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeClanEvent: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeUserStatusPublished: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeUserReceivedNewGame: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypePublishedFile_Announcement: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeModeratorMessage: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeClanCuratedApp: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeQAndASession: _ClassVar[ECommentThreadType]
    k_ECommentThreadTypeMax: _ClassVar[ECommentThreadType]

class EBroadcastPermission(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EBroadcastPermissionDisabled: _ClassVar[EBroadcastPermission]
    k_EBroadcastPermissionFriendsApprove: _ClassVar[EBroadcastPermission]
    k_EBroadcastPermissionFriendsAllowed: _ClassVar[EBroadcastPermission]
    k_EBroadcastPermissionPublic: _ClassVar[EBroadcastPermission]
    k_EBroadcastPermissionSubscribers: _ClassVar[EBroadcastPermission]

class EBroadcastEncoderSetting(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EBroadcastEncoderBestQuality: _ClassVar[EBroadcastEncoderSetting]
    k_EBroadcastEncoderBestPerformance: _ClassVar[EBroadcastEncoderSetting]

class ECloudGamingPlatform(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ECloudGamingPlatformNone: _ClassVar[ECloudGamingPlatform]
    k_ECloudGamingPlatformValve: _ClassVar[ECloudGamingPlatform]
    k_ECloudGamingPlatformNVIDIA: _ClassVar[ECloudGamingPlatform]

class ECompromiseDetectionType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ECompromiseDetectionType_None: _ClassVar[ECompromiseDetectionType]
    k_ECompromiseDetectionType_TradeEvent: _ClassVar[ECompromiseDetectionType]
    k_ECompromiseDetectionType_ApiCallRate: _ClassVar[ECompromiseDetectionType]
    k_ECompromiseDetectionType_Manual: _ClassVar[ECompromiseDetectionType]
    k_ECompromiseDetectionType_TicketAction: _ClassVar[ECompromiseDetectionType]
    k_ECompromiseDetectionType_MaliciousRefund: _ClassVar[ECompromiseDetectionType]
    k_ECompromiseDetectionType_Move2FA: _ClassVar[ECompromiseDetectionType]
    k_ECompromiseDetectionType_DeviceType: _ClassVar[ECompromiseDetectionType]

class EAsyncGameSessionUserState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EAsyncGameSessionUserStateUnknown: _ClassVar[EAsyncGameSessionUserState]
    k_EAsyncGameSessionUserStateWaitingForOthers: _ClassVar[EAsyncGameSessionUserState]
    k_EAsyncGameSessionUserStateReadyForAction: _ClassVar[EAsyncGameSessionUserState]
    k_EAsyncGameSessionUserStateDone: _ClassVar[EAsyncGameSessionUserState]

class EAsyncGameSessionUserVisibility(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EAsyncGameSessionUserVisibilityEnvelopeAndSessionList: _ClassVar[EAsyncGameSessionUserVisibility]
    k_EAsyncGameSessionUserVisibilitySessionListOnly: _ClassVar[EAsyncGameSessionUserVisibility]
    k_EAsyncGameSessionUserVisibilityDismissed: _ClassVar[EAsyncGameSessionUserVisibility]

class EGameRecordingType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EGameRecordingType_Unknown: _ClassVar[EGameRecordingType]
    k_EGameRecordingType_NotRecording: _ClassVar[EGameRecordingType]
    k_EGameRecordingType_ManualRecording: _ClassVar[EGameRecordingType]
    k_EGameRecordingType_BackgroundRecording: _ClassVar[EGameRecordingType]
    k_EGameRecordingType_Clip: _ClassVar[EGameRecordingType]

class EGRMode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EGRMode_Never: _ClassVar[EGRMode]
    k_EGRMode_Always: _ClassVar[EGRMode]
    k_EGRMode_Manual: _ClassVar[EGRMode]

class EExportCodec(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EExportCodec_Default: _ClassVar[EExportCodec]
    k_EExportCodec_H264: _ClassVar[EExportCodec]
    k_EExportCodec_H265: _ClassVar[EExportCodec]

class EProtoAppType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EAppTypeInvalid: _ClassVar[EProtoAppType]
    k_EAppTypeGame: _ClassVar[EProtoAppType]
    k_EAppTypeApplication: _ClassVar[EProtoAppType]
    k_EAppTypeTool: _ClassVar[EProtoAppType]
    k_EAppTypeDemo: _ClassVar[EProtoAppType]
    k_EAppTypeDeprected: _ClassVar[EProtoAppType]
    k_EAppTypeDLC: _ClassVar[EProtoAppType]
    k_EAppTypeGuide: _ClassVar[EProtoAppType]
    k_EAppTypeDriver: _ClassVar[EProtoAppType]
    k_EAppTypeConfig: _ClassVar[EProtoAppType]
    k_EAppTypeHardware: _ClassVar[EProtoAppType]
    k_EAppTypeFranchise: _ClassVar[EProtoAppType]
    k_EAppTypeVideo: _ClassVar[EProtoAppType]
    k_EAppTypePlugin: _ClassVar[EProtoAppType]
    k_EAppTypeMusicAlbum: _ClassVar[EProtoAppType]
    k_EAppTypeSeries: _ClassVar[EProtoAppType]
    k_EAppTypeComic: _ClassVar[EProtoAppType]
    k_EAppTypeBeta: _ClassVar[EProtoAppType]
    k_EAppTypeShortcut: _ClassVar[EProtoAppType]
    k_EAppTypeDepotOnly: _ClassVar[EProtoAppType]

class EAppTestType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EAppTestType_BuildReview: _ClassVar[EAppTestType]
    k_EAppTestType_StorePageReview: _ClassVar[EAppTestType]
    k_EAppTestType_SteamChina_BuildReview: _ClassVar[EAppTestType]
    k_EAppTestType_SteamChina_StorePageReview: _ClassVar[EAppTestType]
    k_EAppTestType_SteamChinaPlatformOperator_StorePageReview: _ClassVar[EAppTestType]
    k_EAppTestType_SteamChinaPlatformOperator_BuildReview: _ClassVar[EAppTestType]
    k_EAppTestType_SteamDeckCompatibilityReview: _ClassVar[EAppTestType]
    k_EAppTestType_SteamFrameCompatibilityReview: _ClassVar[EAppTestType]

class EChildProcessQueryExitCode(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EChildProcessQueryExitCode_Success: _ClassVar[EChildProcessQueryExitCode]
    k_EChildProcessQueryExitCode_ErrorCommandline: _ClassVar[EChildProcessQueryExitCode]
    k_EChildProcessQueryExitCode_ErrorOther: _ClassVar[EChildProcessQueryExitCode]
    k_EChildProcessQueryExitCode_ErrorUnimplemented: _ClassVar[EChildProcessQueryExitCode]
    k_EChildProcessQueryExitCode_ErrorFileSave: _ClassVar[EChildProcessQueryExitCode]
    k_EChildProcessQueryExitCode_ErrorNotSupportedByPlatform: _ClassVar[EChildProcessQueryExitCode]

class EWindowsUpdateInstallationImpact(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EWindowsUpdateInstallationImpact_Unknown: _ClassVar[EWindowsUpdateInstallationImpact]
    k_EWindowsUpdateInstallationImpact_Normal: _ClassVar[EWindowsUpdateInstallationImpact]
    k_EWindowsUpdateInstallationImpact_Minor: _ClassVar[EWindowsUpdateInstallationImpact]
    k_EWindowsUpdateInstallationImpact_ExclusiveHandling: _ClassVar[EWindowsUpdateInstallationImpact]

class EWindowsUpdateRebootBehavior(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EWindowsUpdateRebootBehavior_Unknown: _ClassVar[EWindowsUpdateRebootBehavior]
    k_EWindowsUpdateRebootBehavior_NeverNeedsReboot: _ClassVar[EWindowsUpdateRebootBehavior]
    k_EWindowsUpdateRebootBehavior_AlwaysNeedsReboot: _ClassVar[EWindowsUpdateRebootBehavior]
    k_EWindowsUpdateRebootBehavior_MightNeedReboot: _ClassVar[EWindowsUpdateRebootBehavior]

class EWindowsUpdateOperationResult(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EWindowsUpdateOperationResult_Unknown: _ClassVar[EWindowsUpdateOperationResult]
    k_EWindowsUpdateOperationResult_NotStarted: _ClassVar[EWindowsUpdateOperationResult]
    k_EWindowsUpdateOperationResult_InProgress: _ClassVar[EWindowsUpdateOperationResult]
    k_EWindowsUpdateOperationResult_Succeeded: _ClassVar[EWindowsUpdateOperationResult]
    k_EWindowsUpdateOperationResult_SucceededWithErrors: _ClassVar[EWindowsUpdateOperationResult]
    k_EWindowsUpdateOperationResult_Failed: _ClassVar[EWindowsUpdateOperationResult]
    k_EWindowsUpdateOperationResult_Aborted: _ClassVar[EWindowsUpdateOperationResult]

class EExternalSaleEventType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EExternalSaleEventType_Unknown: _ClassVar[EExternalSaleEventType]
    k_EExternalSaleEventType_Publisher: _ClassVar[EExternalSaleEventType]
    k_EExternalSaleEventType_Showcase: _ClassVar[EExternalSaleEventType]
    k_EExternalSaleEventType_Region: _ClassVar[EExternalSaleEventType]
    k_EExternalSaleEventType_Theme: _ClassVar[EExternalSaleEventType]
    k_EExternalSaleEventType_Franchise: _ClassVar[EExternalSaleEventType]

class EEnhancedMarketAppearanceStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EnhancedMarketAppearanceStatus_None: _ClassVar[EEnhancedMarketAppearanceStatus]
    k_EnhancedMarketAppearanceStatus_Pending: _ClassVar[EEnhancedMarketAppearanceStatus]
    k_EnhancedMarketAppearanceStatus_InProgress: _ClassVar[EEnhancedMarketAppearanceStatus]
    k_EnhancedMarketAppearanceStatus_Completed: _ClassVar[EEnhancedMarketAppearanceStatus]

class EContentReportSubjectType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EContentReportSubjectType_Invalid: _ClassVar[EContentReportSubjectType]
    k_EContentReportSubjectType_ForumPost: _ClassVar[EContentReportSubjectType]
    k_EContentReportSubjectType_CommentThread: _ClassVar[EContentReportSubjectType]
    k_EContentReportSubjectType_UGCFile: _ClassVar[EContentReportSubjectType]
    k_EContentReportSubjectType_FriendChatMsg: _ClassVar[EContentReportSubjectType]
    k_EContentReportSubjectType_ChatRoomMsg: _ClassVar[EContentReportSubjectType]
    k_EContentReportSubjectType_ChatGroup: _ClassVar[EContentReportSubjectType]
    k_EContentReportSubjectType_MAX: _ClassVar[EContentReportSubjectType]

class EControlledLegalCategoryStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EControlledLegalCategoryStatus_None: _ClassVar[EControlledLegalCategoryStatus]
    k_EControlledLegalCategoryStatus_Accused: _ClassVar[EControlledLegalCategoryStatus]
    k_EControlledLegalCategoryStatus_Convicted: _ClassVar[EControlledLegalCategoryStatus]
    k_EControlledLegalCategoryStatus_Acquitted: _ClassVar[EControlledLegalCategoryStatus]

class EContentModeratorLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EContentModeratorLevel_Any: _ClassVar[EContentModeratorLevel]
    k_EContentModeratorLevel_Supervisor: _ClassVar[EContentModeratorLevel]
    k_EContentModeratorLevel_Valve: _ClassVar[EContentModeratorLevel]
    k_EContentModeratorLevel_MAX: _ClassVar[EContentModeratorLevel]

class EContentReportResolution(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EContentReportResolution_Unresolved: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_Acquitted: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_Removed: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_Relabelled: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_Suspicious: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_HarassmentStrike: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_Purged: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_DisconnectedFromApp: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_SuspiciousIncludingUpvoters: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_VisibilityChanged: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_CountryRestrictionsChanged: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_RemoveAndWarn: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_RemoveAndBan: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_RemoveAndKick: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_Sanctioned: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_Sustained: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_Broken: _ClassVar[EContentReportResolution]
    k_EContentReportResolution_MAX: _ClassVar[EContentReportResolution]

class EContentModerationSanction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EContentModerationSanction_Invalid: _ClassVar[EContentModerationSanction]
    k_EContentModerationSanction_Deleted: _ClassVar[EContentModerationSanction]
    k_EContentModerationSanction_CommunityBanned: _ClassVar[EContentModerationSanction]
    k_EContentModerationSanction_HubBanned: _ClassVar[EContentModerationSanction]
    k_EContentModerationSanction_TradeBanned: _ClassVar[EContentModerationSanction]
    k_EContentModerationSanction_CommentHistoryDeleted: _ClassVar[EContentModerationSanction]
    k_EContentModerationSanction_Relabelled: _ClassVar[EContentModerationSanction]
    k_EContentModerationSanction_MarkAsSuspicious: _ClassVar[EContentModerationSanction]
    k_EContentModerationSanction_Warned: _ClassVar[EContentModerationSanction]
    k_EContentModerationSanction_KickedFromGroup: _ClassVar[EContentModerationSanction]
    k_EContentModerationSanction_HarassmentBanned: _ClassVar[EContentModerationSanction]
    k_EContentModerationSanction_HarassmentStrike: _ClassVar[EContentModerationSanction]
    k_EContentModerationSanction_Escalate: _ClassVar[EContentModerationSanction]
    k_EContentModerationSanction_MAX: _ClassVar[EContentModerationSanction]

class EContentReportSubjectAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EContentReportSubjectAction_Invalid: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Unresolved: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Sanctioned: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Acquitted: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Cancelled: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Updated: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Escalated: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Disputed: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Sustained: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Locked: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Unlocked: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Deleted: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Warned: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_BannedFromHub: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_BannedFromCommunity: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_TradeBanned: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_MarkedAsSuspicious: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_ResetContent: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_EscalatedForCSAM: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_EscalatedForTerrorism: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Claimed: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_Released: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_PrivateMessaged: _ClassVar[EContentReportSubjectAction]
    k_EContentReportSubjectAction_OwnerDisputed: _ClassVar[EContentReportSubjectAction]

class EContentReportReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EContentReportReason_Invalid: _ClassVar[EContentReportReason]
    k_EContentReportReason_None: _ClassVar[EContentReportReason]
    k_EContentReportReason_Unknown: _ClassVar[EContentReportReason]
    k_EContentReportReason_Harassment: _ClassVar[EContentReportReason]
    k_EContentReportReason_BullyingAndIntimidation: _ClassVar[EContentReportReason]
    k_EContentReportReason_Stalking: _ClassVar[EContentReportReason]
    k_EContentReportReason_Doxxing: _ClassVar[EContentReportReason]
    k_EContentReportReason_OtherHarassment: _ClassVar[EContentReportReason]
    k_EContentReportReason_EncouragingViolence: _ClassVar[EContentReportReason]
    k_EContentReportReason_EncouragingSelfHarm: _ClassVar[EContentReportReason]
    k_EContentReportReason_EncouragingSuicide: _ClassVar[EContentReportReason]
    k_EContentReportReason_OtherViolenceOrSelfHarm: _ClassVar[EContentReportReason]
    k_EContentReportReason_PhishingOrAccountTheft: _ClassVar[EContentReportReason]
    k_EContentReportReason_AttemptedScamming: _ClassVar[EContentReportReason]
    k_EContentReportReason_LinkingToMaliciousContent: _ClassVar[EContentReportReason]
    k_EContentReportReason_Impersonation: _ClassVar[EContentReportReason]
    k_EContentReportReason_OtherScamsAndTheft: _ClassVar[EContentReportReason]
    k_EContentReportReason_EncouragingTerrorism: _ClassVar[EContentReportReason]
    k_EContentReportReason_OrganizingTerrorism: _ClassVar[EContentReportReason]
    k_EContentReportReason_OtherTerrorism: _ClassVar[EContentReportReason]
    k_EContentReportReason_TargetedAbuse: _ClassVar[EContentReportReason]
    k_EContentReportReason_NamingAndShaming: _ClassVar[EContentReportReason]
    k_EContentReportReason_Discrimination: _ClassVar[EContentReportReason]
    k_EContentReportReason_OtherAbuse: _ClassVar[EContentReportReason]
    k_EContentReportReason_Trolling: _ClassVar[EContentReportReason]
    k_EContentReportReason_Baiting: _ClassVar[EContentReportReason]
    k_EContentReportReason_Derailing: _ClassVar[EContentReportReason]
    k_EContentReportReason_OtherDisruptive: _ClassVar[EContentReportReason]
    k_EContentReportReason_Spam: _ClassVar[EContentReportReason]
    k_EContentReportReason_Begging: _ClassVar[EContentReportReason]
    k_EContentReportReason_Reposting: _ClassVar[EContentReportReason]
    k_EContentReportReason_OtherOffTopic: _ClassVar[EContentReportReason]
    k_EContentReportReason_CSAMSexualContent: _ClassVar[EContentReportReason]
    k_EContentReportReason_CSAMGroomingOrEnticement: _ClassVar[EContentReportReason]
    k_EContentReportReason_CSAMOther: _ClassVar[EContentReportReason]
    k_EContentReportReason_NudityOrSexualContent: _ClassVar[EContentReportReason]
    k_EContentReportReason_NonConsensualMaterial: _ClassVar[EContentReportReason]
    k_EContentReportReason_Advertising: _ClassVar[EContentReportReason]
    k_EContentReportReason_ReferralLinks: _ClassVar[EContentReportReason]
    k_EContentReportReason_Gambling: _ClassVar[EContentReportReason]
    k_EContentReportReason_Raffles: _ClassVar[EContentReportReason]
    k_EContentReportReason_OtherCommercialActivity: _ClassVar[EContentReportReason]
    k_EContentReportReason_InauthenticReview: _ClassVar[EContentReportReason]
    k_EContentReportReason_HiddenAdvertisementOrCommercialCommunication: _ClassVar[EContentReportReason]
    k_EContentReportReason_MisleadingInformationAboutGoodsOrServices: _ClassVar[EContentReportReason]
    k_EContentReportReason_MisleadingInformationAboutConsumerRights: _ClassVar[EContentReportReason]
    k_EContentReportReason_NoncomplianceWithPricingRegulations: _ClassVar[EContentReportReason]
    k_EContentReportReason_RightToBeForgottenViolation: _ClassVar[EContentReportReason]
    k_EContentReportReason_MissingProcessingGroundForData: _ClassVar[EContentReportReason]
    k_EContentReportReason_OtherDataProtectionAndPrivacyViolation: _ClassVar[EContentReportReason]
    k_EContentReportReason_GenderedHarassment: _ClassVar[EContentReportReason]
    k_EContentReportReason_GenderedBullyingAndIntimidation: _ClassVar[EContentReportReason]
    k_EContentReportReason_GenderedStalking: _ClassVar[EContentReportReason]
    k_EContentReportReason_GenderedDoxxing: _ClassVar[EContentReportReason]
    k_EContentReportReason_GenderedOtherHarassment: _ClassVar[EContentReportReason]
    k_EContentReportReason_GenderedEncouragingViolence: _ClassVar[EContentReportReason]
    k_EContentReportReason_GenderedTargetedAbuse: _ClassVar[EContentReportReason]
    k_EContentReportReason_CSAMFakedSexualContent: _ClassVar[EContentReportReason]
    k_EContentReportReason_GenderedNonConsensualMaterial: _ClassVar[EContentReportReason]
    k_EContentReportReason_FakedGenderedNonConsensualMaterial: _ClassVar[EContentReportReason]
    k_EContentReportReason_FakedNonConsensualMaterial: _ClassVar[EContentReportReason]
    k_EContentReportReason_NegativeEffectonDiscourseOrElections: _ClassVar[EContentReportReason]
    k_EContentReportReason_QuotesModeratedContent: _ClassVar[EContentReportReason]
    k_EContentReportReason_CredibleThreatOfViolence: _ClassVar[EContentReportReason]
    k_EContentReportReason_AutoCreatedOnModeration: _ClassVar[EContentReportReason]
    k_EContentReportReason_Piracy: _ClassVar[EContentReportReason]
    k_EContentReportReason_ToSViolation: _ClassVar[EContentReportReason]
    k_EContentReportReason_Miscategorized: _ClassVar[EContentReportReason]
    k_EContentReportReason_BypassingProfanityFilter: _ClassVar[EContentReportReason]
    k_EContentReportReason_BulkDeletion: _ClassVar[EContentReportReason]
    k_EContentReportReason_MAX: _ClassVar[EContentReportReason]

class EResolutionAutomation(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EResolutionAutomation_Manual: _ClassVar[EResolutionAutomation]
    k_EResolutionAutomation_PartiallyAutomated: _ClassVar[EResolutionAutomation]
    k_EResolutionAutomation_FullyAutomated: _ClassVar[EResolutionAutomation]
    k_EResolutionAutomation_MAX: _ClassVar[EResolutionAutomation]

class EPressOutletAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EPressOutletAction_Invalid: _ClassVar[EPressOutletAction]
    k_EPressOutletAction_Granted: _ClassVar[EPressOutletAction]
    k_EPressOutletAction_Removed: _ClassVar[EPressOutletAction]
    k_EPressOutletAction_Created: _ClassVar[EPressOutletAction]
    k_EPressOutletAction_Updated: _ClassVar[EPressOutletAction]
    k_EPressOutletAction_Deleted: _ClassVar[EPressOutletAction]
    k_EPressOutletAction_Undeleted: _ClassVar[EPressOutletAction]
    k_EPressOutletAction_StagedAdd: _ClassVar[EPressOutletAction]
    k_EPressOutletAction_StagedDelete: _ClassVar[EPressOutletAction]
    k_EPressOutletAction_EnterStaging: _ClassVar[EPressOutletAction]
    k_EPressOutletAction_ExitStaging: _ClassVar[EPressOutletAction]
    k_EPressOutletAction_ReverseStagedAdd: _ClassVar[EPressOutletAction]
    k_EPressOutletAction_ReverseStagedDelete: _ClassVar[EPressOutletAction]
    k_EPressOutletAction_MAX: _ClassVar[EPressOutletAction]

class EPressOutletMemberPendingState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EPressOutletMemberPendingState_Member: _ClassVar[EPressOutletMemberPendingState]
    k_EPressOutletMemberPendingState_StagedDelete: _ClassVar[EPressOutletMemberPendingState]
    k_EPressOutletMemberPendingState_StagedAdd: _ClassVar[EPressOutletMemberPendingState]
    k_EPressOutletMemberPendingState_MAX: _ClassVar[EPressOutletMemberPendingState]

class ECommentDeleteReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_ECommentDeleteReason_Invalid: _ClassVar[ECommentDeleteReason]
    k_ECommentDeleteReason_User: _ClassVar[ECommentDeleteReason]
    k_ECommentDeleteReason_ThreadOwner: _ClassVar[ECommentDeleteReason]
    k_ECommentDeleteReason_Moderator: _ClassVar[ECommentDeleteReason]
    k_ECommentDeleteReason_Support: _ClassVar[ECommentDeleteReason]
    k_ECommentDeleteReason_Spam: _ClassVar[ECommentDeleteReason]
    k_ECommentDeleteReason_AccountDeletion: _ClassVar[ECommentDeleteReason]

class EDLCHighlightReason(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    k_EDLCHighlightReason_None: _ClassVar[EDLCHighlightReason]
    k_EDLCHighlightReason_New: _ClassVar[EDLCHighlightReason]
    k_EDLCHighlightReason_ComingSoon: _ClassVar[EDLCHighlightReason]
    k_EDLCHighlightReason_PlayerFavorite: _ClassVar[EDLCHighlightReason]
    k_EDLCHighlightReason_Recommended: _ClassVar[EDLCHighlightReason]
    k_EDLCHighlightReason_NewPlayers: _ClassVar[EDLCHighlightReason]
k_PublishedFileQueryType_RankedByVote: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByPublicationDate: EPublishedFileQueryType
k_PublishedFileQueryType_AcceptedForGameRankedByAcceptanceDate: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByTrend: EPublishedFileQueryType
k_PublishedFileQueryType_FavoritedByFriendsRankedByPublicationDate: EPublishedFileQueryType
k_PublishedFileQueryType_CreatedByFriendsRankedByPublicationDate: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByNumTimesReported: EPublishedFileQueryType
k_PublishedFileQueryType_CreatedByFollowedUsersRankedByPublicationDate: EPublishedFileQueryType
k_PublishedFileQueryType_NotYetRated: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByTotalUniqueSubscriptions: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByTotalVotesAsc: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByVotesUp: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByTextSearch: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByPlaytimeTrend: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByTotalPlaytime: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByAveragePlaytimeTrend: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByLifetimeAveragePlaytime: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByPlaytimeSessionsTrend: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByLifetimePlaytimeSessions: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByInappropriateContentRating: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByBanContentCheck: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByLastUpdatedDate: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByNumParentItems: EPublishedFileQueryType
k_PublishedFileQueryType_RankedByNumParentCollections: EPublishedFileQueryType
k_EPublishedFileInappropriateProvider_Invalid: EPublishedFileInappropriateProvider
k_EPublishedFileInappropriateProvider_Google: EPublishedFileInappropriateProvider
k_EPublishedFileInappropriateProvider_Amazon: EPublishedFileInappropriateProvider
k_EPublishedFileInappropriateResult_NotScanned: EPublishedFileInappropriateResult
k_EPublishedFileInappropriateResult_VeryUnlikely: EPublishedFileInappropriateResult
k_EPublishedFileInappropriateResult_Unlikely: EPublishedFileInappropriateResult
k_EPublishedFileInappropriateResult_Possible: EPublishedFileInappropriateResult
k_EPublishedFileInappropriateResult_Likely: EPublishedFileInappropriateResult
k_EPublishedFileInappropriateResult_VeryLikely: EPublishedFileInappropriateResult
k_EPersonaStateFlag_HasRichPresence: EPersonaStateFlag
k_EPersonaStateFlag_InJoinableGame: EPersonaStateFlag
k_EPersonaStateFlag_Golden: EPersonaStateFlag
k_EPersonaStateFlag_RemotePlayTogether: EPersonaStateFlag
k_EPersonaStateFlag_ClientTypeWeb: EPersonaStateFlag
k_EPersonaStateFlag_ClientTypeMobile: EPersonaStateFlag
k_EPersonaStateFlag_ClientTypeTenfoot: EPersonaStateFlag
k_EPersonaStateFlag_ClientTypeVR: EPersonaStateFlag
k_EPersonaStateFlag_LaunchTypeGamepad: EPersonaStateFlag
k_EPersonaStateFlag_LaunchTypeCompatTool: EPersonaStateFlag
k_EContentCheckProvider_Invalid: EContentCheckProvider
k_EContentCheckProvider_Google_DEPRECATED: EContentCheckProvider
k_EContentCheckProvider_Amazon: EContentCheckProvider
k_EContentCheckProvider_Local: EContentCheckProvider
k_EContentCheckProvider_GoogleVertexAI: EContentCheckProvider
k_EContentCheckProvider_GoogleGemini: EContentCheckProvider
k_EContentCheckProvider_SteamLearn: EContentCheckProvider
k_EProfileCustomizationTypeInvalid: EProfileCustomizationType
k_EProfileCustomizationTypeRareAchievementShowcase: EProfileCustomizationType
k_EProfileCustomizationTypeGameCollector: EProfileCustomizationType
k_EProfileCustomizationTypeItemShowcase: EProfileCustomizationType
k_EProfileCustomizationTypeTradeShowcase: EProfileCustomizationType
k_EProfileCustomizationTypeBadges: EProfileCustomizationType
k_EProfileCustomizationTypeFavoriteGame: EProfileCustomizationType
k_EProfileCustomizationTypeScreenshotShowcase: EProfileCustomizationType
k_EProfileCustomizationTypeCustomText: EProfileCustomizationType
k_EProfileCustomizationTypeFavoriteGroup: EProfileCustomizationType
k_EProfileCustomizationTypeRecommendation: EProfileCustomizationType
k_EProfileCustomizationTypeWorkshopItem: EProfileCustomizationType
k_EProfileCustomizationTypeMyWorkshop: EProfileCustomizationType
k_EProfileCustomizationTypeArtworkShowcase: EProfileCustomizationType
k_EProfileCustomizationTypeVideoShowcase: EProfileCustomizationType
k_EProfileCustomizationTypeGuides: EProfileCustomizationType
k_EProfileCustomizationTypeMyGuides: EProfileCustomizationType
k_EProfileCustomizationTypeAchievements: EProfileCustomizationType
k_EProfileCustomizationTypeGreenlight: EProfileCustomizationType
k_EProfileCustomizationTypeMyGreenlight: EProfileCustomizationType
k_EProfileCustomizationTypeSalien: EProfileCustomizationType
k_EProfileCustomizationTypeLoyaltyRewardReactions: EProfileCustomizationType
k_EProfileCustomizationTypeSingleArtworkShowcase: EProfileCustomizationType
k_EProfileCustomizationTypeAchievementsCompletionist: EProfileCustomizationType
k_EProfileCustomizationTypeReplay: EProfileCustomizationType
k_EPublishedFileStorageSystemInvalid: EPublishedFileStorageSystem
k_EPublishedFileStorageSystemLegacyCloud: EPublishedFileStorageSystem
k_EPublishedFileStorageSystemDepot: EPublishedFileStorageSystem
k_EPublishedFileStorageSystemUGCCloud: EPublishedFileStorageSystem
k_ECloudStoragePersistStatePersisted: ECloudStoragePersistState
k_ECloudStoragePersistStateForgotten: ECloudStoragePersistState
k_ECloudStoragePersistStateDeleted: ECloudStoragePersistState
k_ESDCardFormatStage_Invalid: ESDCardFormatStage
k_ESDCardFormatStage_Starting: ESDCardFormatStage
k_ESDCardFormatStage_Testing: ESDCardFormatStage
k_ESDCardFormatStage_Rescuing: ESDCardFormatStage
k_ESDCardFormatStage_Formatting: ESDCardFormatStage
k_ESDCardFormatStage_Finalizing: ESDCardFormatStage
k_EStorageFormatStage_Invalid: EStorageFormatStage
k_EStorageFormatStage_NotRunning: EStorageFormatStage
k_EStorageFormatStage_Starting: EStorageFormatStage
k_EStorageFormatStage_Testing: EStorageFormatStage
k_EStorageFormatStage_Rescuing: EStorageFormatStage
k_EStorageFormatStage_Formatting: EStorageFormatStage
k_EStorageFormatStage_Finalizing: EStorageFormatStage
k_SystemFanControlMode_Invalid: ESystemFanControlMode
k_SystemFanControlMode_Disabled: ESystemFanControlMode
k_SystemFanControlMode_Default: ESystemFanControlMode
k_ColorGamutLabelSet_Default: EColorGamutLabelSet
k_ColorGamutLabelSet_sRGB_Native: EColorGamutLabelSet
k_ColorGamutLabelSet_Native_sRGB_Boosted: EColorGamutLabelSet
k_EWindowStackingOrder_Invalid: EWindowStackingOrder
k_EWindowStackingOrder_Top: EWindowStackingOrder
k_EWindowStackingOrder_Bottom: EWindowStackingOrder
k_BluetoothDeviceType_Invalid: EBluetoothDeviceType
k_BluetoothDeviceType_Unknown: EBluetoothDeviceType
k_BluetoothDeviceType_Phone: EBluetoothDeviceType
k_BluetoothDeviceType_Computer: EBluetoothDeviceType
k_BluetoothDeviceType_Headset: EBluetoothDeviceType
k_BluetoothDeviceType_Headphones: EBluetoothDeviceType
k_BluetoothDeviceType_Speakers: EBluetoothDeviceType
k_BluetoothDeviceType_OtherAudio: EBluetoothDeviceType
k_BluetoothDeviceType_Mouse: EBluetoothDeviceType
k_BluetoothDeviceType_Joystick: EBluetoothDeviceType
k_BluetoothDeviceType_Gamepad: EBluetoothDeviceType
k_BluetoothDeviceType_Keyboard: EBluetoothDeviceType
k_ESpeakerConfiguration_Other: ESpeakerConfiguration
k_ESpeakerConfiguration_Stereo: ESpeakerConfiguration
k_ESpeakerConfiguration_51: ESpeakerConfiguration
k_ESpeakerConfiguration_71: ESpeakerConfiguration
k_ESpeakerConfiguration_51_Ac3: ESpeakerConfiguration
k_SystemAudioDirection_Invalid: ESystemAudioDirection
k_SystemAudioDirection_Input: ESystemAudioDirection
k_SystemAudioDirection_Output: ESystemAudioDirection
k_SystemAudioChannel_Invalid: ESystemAudioChannel
k_SystemAudioChannel_Aggregated: ESystemAudioChannel
k_SystemAudioChannel_FrontLeft: ESystemAudioChannel
k_SystemAudioChannel_FrontRight: ESystemAudioChannel
k_SystemAudioChannel_LFE: ESystemAudioChannel
k_SystemAudioChannel_BackLeft: ESystemAudioChannel
k_SystemAudioChannel_BackRight: ESystemAudioChannel
k_SystemAudioChannel_FrontCenter: ESystemAudioChannel
k_SystemAudioChannel_Unknown: ESystemAudioChannel
k_SystemAudioChannel_Mono: ESystemAudioChannel
k_SystemAudioPortType_Invalid: ESystemAudioPortType
k_SystemAudioPortType_Unknown: ESystemAudioPortType
k_SystemAudioPortType_Audio32f: ESystemAudioPortType
k_SystemAudioPortType_Midi8b: ESystemAudioPortType
k_SystemAudioPortType_Video32RGBA: ESystemAudioPortType
k_SystemAudioPortDirection_Invalid: ESystemAudioPortDirection
k_SystemAudioPortDirection_Input: ESystemAudioPortDirection
k_SystemAudioPortDirection_Output: ESystemAudioPortDirection
k_ESystemServiceState_Unavailable: ESystemServiceState
k_ESystemServiceState_Disabled: ESystemServiceState
k_ESystemServiceState_Enabled: ESystemServiceState
k_EBluetoothAudioPreference_Quality: EBluetoothAudioPreference
k_EBluetoothAudioPreference_Latency: EBluetoothAudioPreference
k_EGraphicsPerfOverlayLevel_Hidden: EGraphicsPerfOverlayLevel
k_EGraphicsPerfOverlayLevel_Basic: EGraphicsPerfOverlayLevel
k_EGraphicsPerfOverlayLevel_Medium: EGraphicsPerfOverlayLevel
k_EGraphicsPerfOverlayLevel_Full: EGraphicsPerfOverlayLevel
k_EGraphicsPerfOverlayLevel_Minimal: EGraphicsPerfOverlayLevel
k_EGPUPerformanceLevel_Invalid: EGPUPerformanceLevel
k_EGPUPerformanceLevel_Auto: EGPUPerformanceLevel
k_EGPUPerformanceLevel_Manual: EGPUPerformanceLevel
k_EGPUPerformanceLevel_Low: EGPUPerformanceLevel
k_EGPUPerformanceLevel_High: EGPUPerformanceLevel
k_EGPUPerformanceLevel_Profiling: EGPUPerformanceLevel
k_ESplitScalingFilter_Invalid: ESplitScalingFilter
k_ESplitScalingFilter_Linear: ESplitScalingFilter
k_ESplitScalingFilter_Nearest: ESplitScalingFilter
k_ESplitScalingFilter_Sharp: ESplitScalingFilter
k_ESplitScalingFilter_NIS_Deprecated: ESplitScalingFilter
k_ESplitScalingScaler_Invalid: ESplitScalingScaler
k_ESplitScalingScaler_Auto: ESplitScalingScaler
k_ESplitScalingScaler_Integer: ESplitScalingScaler
k_ESplitScalingScaler_Fit: ESplitScalingScaler
k_ESplitScalingScaler_Fill: ESplitScalingScaler
k_ESplitScalingScaler_Stretch: ESplitScalingScaler
k_EGamescopeBlurMode_Disabled: EGamescopeBlurMode
k_EGamescopeBlurMode_IfOccluded: EGamescopeBlurMode
k_EGamescopeBlurMode_Always: EGamescopeBlurMode
k_ESLSHelper_Invalid: ESLSHelper
k_ESLSHelper_Minidump: ESLSHelper
k_ESLSHelper_Kdump: ESLSHelper
k_ESLSHelper_Journal: ESLSHelper
k_ESLSHelper_Gpu: ESLSHelper
k_ESLSHelper_SystemInfo: ESLSHelper
k_ESLSHelper_Devcoredump: ESLSHelper
k_EHDRVisualization_None: EHDRVisualization
k_EHDRVisualization_Heatmap: EHDRVisualization
k_EHDRVisualization_Analysis: EHDRVisualization
k_EHDRVisualization_HeatmapExtended: EHDRVisualization
k_EHDRVisualization_HeatmapClassic: EHDRVisualization
k_EHDRToneMapOperator_Invalid: EHDRToneMapOperator
k_EHDRToneMapOperator_Uncharted: EHDRToneMapOperator
k_EHDRToneMapOperator_Reinhard: EHDRToneMapOperator
k_ECPUGovernor_Invalid: ECPUGovernor
k_ECPUGovernor_Perf: ECPUGovernor
k_ECPUGovernor_Powersave: ECPUGovernor
k_ECPUGovernor_Manual: ECPUGovernor
k_EUpdaterType_Invalid: EUpdaterType
k_EUpdaterType_Client: EUpdaterType
k_EUpdaterType_OS: EUpdaterType
k_EUpdaterType_BIOS: EUpdaterType
k_EUpdaterType_Aggregated: EUpdaterType
k_EUpdaterType_Test1: EUpdaterType
k_EUpdaterType_Test2: EUpdaterType
k_EUpdaterType_Dummy: EUpdaterType
k_EUpdaterState_Invalid: EUpdaterState
k_EUpdaterState_UpToDate: EUpdaterState
k_EUpdaterState_Checking: EUpdaterState
k_EUpdaterState_Available: EUpdaterState
k_EUpdaterState_Applying: EUpdaterState
k_EUpdaterState_ClientRestartPending: EUpdaterState
k_EUpdaterState_SystemRestartPending: EUpdaterState
k_EUpdaterState_RollBack: EUpdaterState
k_EStorageBlockContentType_Invalid: EStorageBlockContentType
k_EStorageBlockContentType_Unknown: EStorageBlockContentType
k_EStorageBlockContentType_FileSystem: EStorageBlockContentType
k_EStorageBlockContentType_Crypto: EStorageBlockContentType
k_EStorageBlockContentType_Raid: EStorageBlockContentType
k_EStorageBlockFileSystemType_Invalid: EStorageBlockFileSystemType
k_EStorageBlockFileSystemType_Unknown: EStorageBlockFileSystemType
k_EStorageBlockFileSystemType_VFat: EStorageBlockFileSystemType
k_EStorageBlockFileSystemType_Ext4: EStorageBlockFileSystemType
k_EStorageDriveMediaType_Invalid: EStorageDriveMediaType
k_EStorageDriveMediaType_Unknown: EStorageDriveMediaType
k_EStorageDriveMediaType_HDD: EStorageDriveMediaType
k_EStorageDriveMediaType_SSD: EStorageDriveMediaType
k_EStorageDriveMediaType_Removable: EStorageDriveMediaType
k_ESystemDisplayCompatibilityMode_Invalid: ESystemDisplayCompatibilityMode
k_ESystemDisplayCompatibilityMode_None: ESystemDisplayCompatibilityMode
k_ESystemDisplayCompatibilityMode_MinimalBandwith: ESystemDisplayCompatibilityMode
k_ESteamOSCompatibilityCategory_Unknown: ESteamOSCompatibilityCategory
k_ESteamOSCompatibilityCategory_Unsupported: ESteamOSCompatibilityCategory
k_ESteamOSCompatibilityCategory_Compatible: ESteamOSCompatibilityCategory
k_ESteamOSCompatibilityResultDisplayType_Invisible: ESteamOSCompatibilityResultDisplayType
k_ESteamOSCompatibilityResultDisplayType_Informational: ESteamOSCompatibilityResultDisplayType
k_ESteamOSCompatibilityResultDisplayType_Unsupported: ESteamOSCompatibilityResultDisplayType
k_ESteamOSCompatibilityResultDisplayType_Compatible: ESteamOSCompatibilityResultDisplayType
k_ESteamDeckCompatibilityCategory_Unknown: ESteamDeckCompatibilityCategory
k_ESteamDeckCompatibilityCategory_Unsupported: ESteamDeckCompatibilityCategory
k_ESteamDeckCompatibilityCategory_Playable: ESteamDeckCompatibilityCategory
k_ESteamDeckCompatibilityCategory_Verified: ESteamDeckCompatibilityCategory
k_ESteamDeckCompatibilityResultDisplayType_Invisible: ESteamDeckCompatibilityResultDisplayType
k_ESteamDeckCompatibilityResultDisplayType_Informational: ESteamDeckCompatibilityResultDisplayType
k_ESteamDeckCompatibilityResultDisplayType_Unsupported: ESteamDeckCompatibilityResultDisplayType
k_ESteamDeckCompatibilityResultDisplayType_Playable: ESteamDeckCompatibilityResultDisplayType
k_ESteamDeckCompatibilityResultDisplayType_Verified: ESteamDeckCompatibilityResultDisplayType
k_ESteamDeckCompatibilityTestResult_Invalid: ESteamDeckCompatibilityTestResult
k_ESteamDeckCompatibilityTestResult_NotApplicable: ESteamDeckCompatibilityTestResult
k_ESteamDeckCompatibilityTestResult_Pass: ESteamDeckCompatibilityTestResult
k_ESteamDeckCompatibilityTestResult_Fail: ESteamDeckCompatibilityTestResult
k_ESteamDeckCompatibilityTestResult_FailMinor: ESteamDeckCompatibilityTestResult
k_EACState_Unknown: EACState
k_EACState_Disconnected: EACState
k_EACState_Connected: EACState
k_EACState_ConnectedSlow: EACState
k_EBatteryState_Unknown: EBatteryState
k_EBatteryState_Discharging: EBatteryState
k_EBatteryState_Charging: EBatteryState
k_EBatteryState_Full: EBatteryState
k_EOSBranch_Unknown: EOSBranch
k_EOSBranch_Release: EOSBranch
k_EOSBranch_ReleaseCandidate: EOSBranch
k_EOSBranch_Beta: EOSBranch
k_EOSBranch_BetaCandidate: EOSBranch
k_EOSBranch_Preview: EOSBranch
k_EOSBranch_PreviewCandidate: EOSBranch
k_EOSBranch_Main: EOSBranch
k_EOSBranch_Staging: EOSBranch
k_EBrowserGPUStatus_Invalid: EBrowserGPUStatus
k_EBrowserGPUStatus_Enabled: EBrowserGPUStatus
k_EBrowserGPUStatus_DisabledUnknown: EBrowserGPUStatus
k_EBrowserGPUStatus_DisabledCrashCount: EBrowserGPUStatus
k_EBrowserGPUStatus_DisabledBlocklist: EBrowserGPUStatus
k_EBrowserGPUStatus_DisabledJSRequest: EBrowserGPUStatus
k_EBrowserGPUStatus_DisabledCommandLine: EBrowserGPUStatus
k_EBrowserGPUStatus_DisabledRuntimeDetect: EBrowserGPUStatus
k_EBrowserGPUStatus_DisabledChildCommandLine: EBrowserGPUStatus
k_EBrowserGPUStatus_DisabledCompositingCommandLine: EBrowserGPUStatus
k_EBrowserFeatureStatus_Invalid: EBrowserFeatureStatus
k_EBrowserFeatureStatus_NotFound: EBrowserFeatureStatus
k_EBrowserFeatureStatus_Unknown: EBrowserFeatureStatus
k_EBrowserFeatureStatus_DisabledSoftware: EBrowserFeatureStatus
k_EBrowserFeatureStatus_DisabledOff: EBrowserFeatureStatus
k_EBrowserFeatureStatus_DisabledOffOk: EBrowserFeatureStatus
k_EBrowserFeatureStatus_UnavailableSoftware: EBrowserFeatureStatus
k_EBrowserFeatureStatus_UnavailableOff: EBrowserFeatureStatus
k_EBrowserFeatureStatus_UnavailableOffOk: EBrowserFeatureStatus
k_EBrowserFeatureStatus_EnabledReadback: EBrowserFeatureStatus
k_EBrowserFeatureStatus_EnabledForce: EBrowserFeatureStatus
k_EBrowserFeatureStatus_Enabled: EBrowserFeatureStatus
k_EBrowserFeatureStatus_EnabledOn: EBrowserFeatureStatus
k_EBrowserFeatureStatus_EnabledForceOn: EBrowserFeatureStatus
k_EGpuDriverId_Invalid: EGpuDriverId
k_EGpuDriverId_Unknown: EGpuDriverId
k_EGpuDriverId_AmdProprietary: EGpuDriverId
k_EGpuDriverId_AmdOpenSource: EGpuDriverId
k_EGpuDriverId_MesaRadv: EGpuDriverId
k_EGpuDriverId_NvidiaProprietary: EGpuDriverId
k_EGpuDriverId_IntelPropietary: EGpuDriverId
k_EGpuDriverId_MesaIntel: EGpuDriverId
k_EGpuDriverId_QualcommProprietary: EGpuDriverId
k_EGpuDriverId_ArmProprietary: EGpuDriverId
k_EGpuDriverId_GoogleSwiftshader: EGpuDriverId
k_EGpuDriverId_BroadcomProprietary: EGpuDriverId
k_EGpuDriverId_MesaLLVMPipe: EGpuDriverId
k_EGpuDriverId_MoltenVK: EGpuDriverId
k_EGpuDriverId_MesaTurnip: EGpuDriverId
k_EGpuDriverId_MesaPanVK: EGpuDriverId
k_EGpuDriverId_MesaVenus: EGpuDriverId
k_EGpuDriverId_MesaDozen: EGpuDriverId
k_EGpuDriverId_MesaNVK: EGpuDriverId
k_EGpuDriverId_MesaHoneyKrisp: EGpuDriverId
k_ECommunityItemClass_Invalid: ECommunityItemClass
k_ECommunityItemClass_Badge: ECommunityItemClass
k_ECommunityItemClass_GameCard: ECommunityItemClass
k_ECommunityItemClass_ProfileBackground: ECommunityItemClass
k_ECommunityItemClass_Emoticon: ECommunityItemClass
k_ECommunityItemClass_BoosterPack: ECommunityItemClass
k_ECommunityItemClass_Consumable: ECommunityItemClass
k_ECommunityItemClass_GameGoo: ECommunityItemClass
k_ECommunityItemClass_ProfileModifier: ECommunityItemClass
k_ECommunityItemClass_Scene: ECommunityItemClass
k_ECommunityItemClass_SalienItem: ECommunityItemClass
k_ECommunityItemClass_Sticker: ECommunityItemClass
k_ECommunityItemClass_ChatEffect: ECommunityItemClass
k_ECommunityItemClass_MiniProfileBackground: ECommunityItemClass
k_ECommunityItemClass_AvatarFrame: ECommunityItemClass
k_ECommunityItemClass_AnimatedAvatar: ECommunityItemClass
k_ECommunityItemClass_SteamDeckKeyboardSkin: ECommunityItemClass
k_ECommunityItemClass_SteamDeckStartupMovie: ECommunityItemClass
k_ESteamDeckCompatibilityFeedback_Unset: ESteamDeckCompatibilityFeedback
k_ESteamDeckCompatibilityFeedback_Agree: ESteamDeckCompatibilityFeedback
k_ESteamDeckCompatibilityFeedback_Disagree: ESteamDeckCompatibilityFeedback
k_ESteamDeckCompatibilityFeedback_Ignore: ESteamDeckCompatibilityFeedback
k_EProvideDeckFeedbackPreference_Unset: EProvideDeckFeedbackPreference
k_EProvideDeckFeedbackPreference_Yes: EProvideDeckFeedbackPreference
k_EProvideDeckFeedbackPreference_No: EProvideDeckFeedbackPreference
k_EHardwareCompatibilityFeedbackDetails_Unset: EHardwareCompatibilityFeedbackDetails
k_EHardwareCompatibilityFeedbackDetails_Performance: EHardwareCompatibilityFeedbackDetails
k_EHardwareCompatibilityFeedbackDetails_Stability: EHardwareCompatibilityFeedbackDetails
k_EHardwareCompatibilityFeedbackDetails_Legibility: EHardwareCompatibilityFeedbackDetails
k_EHardwareCompatibilityFeedbackDetails_Input: EHardwareCompatibilityFeedbackDetails
k_EHardwareCompatibilityFeedbackDetails_Other: EHardwareCompatibilityFeedbackDetails
k_EGameFrameRateReportingPreference_Unset: EGameFrameRateReportingPreference
k_EGameFrameRateReportingPreference_No: EGameFrameRateReportingPreference
k_EGameFrameRateReportingPreference_Yes_Anonymous: EGameFrameRateReportingPreference
k_EGameFrameRateReportingPreference_Yes_NonAnonymous: EGameFrameRateReportingPreference
k_ETouchGestureNone: ETouchGesture
k_ETouchGestureTouch: ETouchGesture
k_ETouchGestureTap: ETouchGesture
k_ETouchGestureDoubleTap: ETouchGesture
k_ETouchGestureShortPress: ETouchGesture
k_ETouchGestureLongPress: ETouchGesture
k_ETouchGestureLongTap: ETouchGesture
k_ETouchGestureTwoFingerTap: ETouchGesture
k_ETouchGestureTapCancelled: ETouchGesture
k_ETouchGesturePinchBegin: ETouchGesture
k_ETouchGesturePinchUpdate: ETouchGesture
k_ETouchGesturePinchEnd: ETouchGesture
k_ETouchGestureFlingStart: ETouchGesture
k_ETouchGestureFlingCancelled: ETouchGesture
k_ESessionPersistence_Invalid: ESessionPersistence
k_ESessionPersistence_Ephemeral: ESessionPersistence
k_ESessionPersistence_Persistent: ESessionPersistence
k_ENewSteamAnnouncementState_Invalid: ENewSteamAnnouncementState
k_ENewSteamAnnouncementState_AllRead: ENewSteamAnnouncementState
k_ENewSteamAnnouncementState_NewAnnouncement: ENewSteamAnnouncementState
k_ENewSteamAnnouncementState_FeaturedAnnouncement: ENewSteamAnnouncementState
k_EForumType_Invalid: EForumType
k_EForumType_General: EForumType
k_EForumType_ReportedPosts: EForumType
k_EForumType_Workshop: EForumType
k_EForumType_PublishedFile: EForumType
k_EForumType_Trading: EForumType
k_EForumType_PlayTest: EForumType
k_EForumType_Event: EForumType
k_EForumType_Max: EForumType
k_ECommentThreadTypeInvalid: ECommentThreadType
k_ECommentThreadTypeScreenshot_Deprecated: ECommentThreadType
k_ECommentThreadTypeWorkshopAccount_Developer: ECommentThreadType
k_ECommentThreadTypeWorkshopAccount_Public: ECommentThreadType
k_ECommentThreadTypePublishedFile_Developer: ECommentThreadType
k_ECommentThreadTypePublishedFile_Public: ECommentThreadType
k_ECommentThreadTypeTest: ECommentThreadType
k_ECommentThreadTypeForumTopic: ECommentThreadType
k_ECommentThreadTypeRecommendation: ECommentThreadType
k_ECommentThreadTypeVideo_Deprecated: ECommentThreadType
k_ECommentThreadTypeProfile: ECommentThreadType
k_ECommentThreadTypeNewsPost: ECommentThreadType
k_ECommentThreadTypeClan: ECommentThreadType
k_ECommentThreadTypeClanAnnouncement: ECommentThreadType
k_ECommentThreadTypeClanEvent: ECommentThreadType
k_ECommentThreadTypeUserStatusPublished: ECommentThreadType
k_ECommentThreadTypeUserReceivedNewGame: ECommentThreadType
k_ECommentThreadTypePublishedFile_Announcement: ECommentThreadType
k_ECommentThreadTypeModeratorMessage: ECommentThreadType
k_ECommentThreadTypeClanCuratedApp: ECommentThreadType
k_ECommentThreadTypeQAndASession: ECommentThreadType
k_ECommentThreadTypeMax: ECommentThreadType
k_EBroadcastPermissionDisabled: EBroadcastPermission
k_EBroadcastPermissionFriendsApprove: EBroadcastPermission
k_EBroadcastPermissionFriendsAllowed: EBroadcastPermission
k_EBroadcastPermissionPublic: EBroadcastPermission
k_EBroadcastPermissionSubscribers: EBroadcastPermission
k_EBroadcastEncoderBestQuality: EBroadcastEncoderSetting
k_EBroadcastEncoderBestPerformance: EBroadcastEncoderSetting
k_ECloudGamingPlatformNone: ECloudGamingPlatform
k_ECloudGamingPlatformValve: ECloudGamingPlatform
k_ECloudGamingPlatformNVIDIA: ECloudGamingPlatform
k_ECompromiseDetectionType_None: ECompromiseDetectionType
k_ECompromiseDetectionType_TradeEvent: ECompromiseDetectionType
k_ECompromiseDetectionType_ApiCallRate: ECompromiseDetectionType
k_ECompromiseDetectionType_Manual: ECompromiseDetectionType
k_ECompromiseDetectionType_TicketAction: ECompromiseDetectionType
k_ECompromiseDetectionType_MaliciousRefund: ECompromiseDetectionType
k_ECompromiseDetectionType_Move2FA: ECompromiseDetectionType
k_ECompromiseDetectionType_DeviceType: ECompromiseDetectionType
k_EAsyncGameSessionUserStateUnknown: EAsyncGameSessionUserState
k_EAsyncGameSessionUserStateWaitingForOthers: EAsyncGameSessionUserState
k_EAsyncGameSessionUserStateReadyForAction: EAsyncGameSessionUserState
k_EAsyncGameSessionUserStateDone: EAsyncGameSessionUserState
k_EAsyncGameSessionUserVisibilityEnvelopeAndSessionList: EAsyncGameSessionUserVisibility
k_EAsyncGameSessionUserVisibilitySessionListOnly: EAsyncGameSessionUserVisibility
k_EAsyncGameSessionUserVisibilityDismissed: EAsyncGameSessionUserVisibility
k_EGameRecordingType_Unknown: EGameRecordingType
k_EGameRecordingType_NotRecording: EGameRecordingType
k_EGameRecordingType_ManualRecording: EGameRecordingType
k_EGameRecordingType_BackgroundRecording: EGameRecordingType
k_EGameRecordingType_Clip: EGameRecordingType
k_EGRMode_Never: EGRMode
k_EGRMode_Always: EGRMode
k_EGRMode_Manual: EGRMode
k_EExportCodec_Default: EExportCodec
k_EExportCodec_H264: EExportCodec
k_EExportCodec_H265: EExportCodec
k_EAppTypeInvalid: EProtoAppType
k_EAppTypeGame: EProtoAppType
k_EAppTypeApplication: EProtoAppType
k_EAppTypeTool: EProtoAppType
k_EAppTypeDemo: EProtoAppType
k_EAppTypeDeprected: EProtoAppType
k_EAppTypeDLC: EProtoAppType
k_EAppTypeGuide: EProtoAppType
k_EAppTypeDriver: EProtoAppType
k_EAppTypeConfig: EProtoAppType
k_EAppTypeHardware: EProtoAppType
k_EAppTypeFranchise: EProtoAppType
k_EAppTypeVideo: EProtoAppType
k_EAppTypePlugin: EProtoAppType
k_EAppTypeMusicAlbum: EProtoAppType
k_EAppTypeSeries: EProtoAppType
k_EAppTypeComic: EProtoAppType
k_EAppTypeBeta: EProtoAppType
k_EAppTypeShortcut: EProtoAppType
k_EAppTypeDepotOnly: EProtoAppType
k_EAppTestType_BuildReview: EAppTestType
k_EAppTestType_StorePageReview: EAppTestType
k_EAppTestType_SteamChina_BuildReview: EAppTestType
k_EAppTestType_SteamChina_StorePageReview: EAppTestType
k_EAppTestType_SteamChinaPlatformOperator_StorePageReview: EAppTestType
k_EAppTestType_SteamChinaPlatformOperator_BuildReview: EAppTestType
k_EAppTestType_SteamDeckCompatibilityReview: EAppTestType
k_EAppTestType_SteamFrameCompatibilityReview: EAppTestType
k_EChildProcessQueryExitCode_Success: EChildProcessQueryExitCode
k_EChildProcessQueryExitCode_ErrorCommandline: EChildProcessQueryExitCode
k_EChildProcessQueryExitCode_ErrorOther: EChildProcessQueryExitCode
k_EChildProcessQueryExitCode_ErrorUnimplemented: EChildProcessQueryExitCode
k_EChildProcessQueryExitCode_ErrorFileSave: EChildProcessQueryExitCode
k_EChildProcessQueryExitCode_ErrorNotSupportedByPlatform: EChildProcessQueryExitCode
k_EWindowsUpdateInstallationImpact_Unknown: EWindowsUpdateInstallationImpact
k_EWindowsUpdateInstallationImpact_Normal: EWindowsUpdateInstallationImpact
k_EWindowsUpdateInstallationImpact_Minor: EWindowsUpdateInstallationImpact
k_EWindowsUpdateInstallationImpact_ExclusiveHandling: EWindowsUpdateInstallationImpact
k_EWindowsUpdateRebootBehavior_Unknown: EWindowsUpdateRebootBehavior
k_EWindowsUpdateRebootBehavior_NeverNeedsReboot: EWindowsUpdateRebootBehavior
k_EWindowsUpdateRebootBehavior_AlwaysNeedsReboot: EWindowsUpdateRebootBehavior
k_EWindowsUpdateRebootBehavior_MightNeedReboot: EWindowsUpdateRebootBehavior
k_EWindowsUpdateOperationResult_Unknown: EWindowsUpdateOperationResult
k_EWindowsUpdateOperationResult_NotStarted: EWindowsUpdateOperationResult
k_EWindowsUpdateOperationResult_InProgress: EWindowsUpdateOperationResult
k_EWindowsUpdateOperationResult_Succeeded: EWindowsUpdateOperationResult
k_EWindowsUpdateOperationResult_SucceededWithErrors: EWindowsUpdateOperationResult
k_EWindowsUpdateOperationResult_Failed: EWindowsUpdateOperationResult
k_EWindowsUpdateOperationResult_Aborted: EWindowsUpdateOperationResult
k_EExternalSaleEventType_Unknown: EExternalSaleEventType
k_EExternalSaleEventType_Publisher: EExternalSaleEventType
k_EExternalSaleEventType_Showcase: EExternalSaleEventType
k_EExternalSaleEventType_Region: EExternalSaleEventType
k_EExternalSaleEventType_Theme: EExternalSaleEventType
k_EExternalSaleEventType_Franchise: EExternalSaleEventType
k_EnhancedMarketAppearanceStatus_None: EEnhancedMarketAppearanceStatus
k_EnhancedMarketAppearanceStatus_Pending: EEnhancedMarketAppearanceStatus
k_EnhancedMarketAppearanceStatus_InProgress: EEnhancedMarketAppearanceStatus
k_EnhancedMarketAppearanceStatus_Completed: EEnhancedMarketAppearanceStatus
k_EContentReportSubjectType_Invalid: EContentReportSubjectType
k_EContentReportSubjectType_ForumPost: EContentReportSubjectType
k_EContentReportSubjectType_CommentThread: EContentReportSubjectType
k_EContentReportSubjectType_UGCFile: EContentReportSubjectType
k_EContentReportSubjectType_FriendChatMsg: EContentReportSubjectType
k_EContentReportSubjectType_ChatRoomMsg: EContentReportSubjectType
k_EContentReportSubjectType_ChatGroup: EContentReportSubjectType
k_EContentReportSubjectType_MAX: EContentReportSubjectType
k_EControlledLegalCategoryStatus_None: EControlledLegalCategoryStatus
k_EControlledLegalCategoryStatus_Accused: EControlledLegalCategoryStatus
k_EControlledLegalCategoryStatus_Convicted: EControlledLegalCategoryStatus
k_EControlledLegalCategoryStatus_Acquitted: EControlledLegalCategoryStatus
k_EContentModeratorLevel_Any: EContentModeratorLevel
k_EContentModeratorLevel_Supervisor: EContentModeratorLevel
k_EContentModeratorLevel_Valve: EContentModeratorLevel
k_EContentModeratorLevel_MAX: EContentModeratorLevel
k_EContentReportResolution_Unresolved: EContentReportResolution
k_EContentReportResolution_Acquitted: EContentReportResolution
k_EContentReportResolution_Removed: EContentReportResolution
k_EContentReportResolution_Relabelled: EContentReportResolution
k_EContentReportResolution_Suspicious: EContentReportResolution
k_EContentReportResolution_HarassmentStrike: EContentReportResolution
k_EContentReportResolution_Purged: EContentReportResolution
k_EContentReportResolution_DisconnectedFromApp: EContentReportResolution
k_EContentReportResolution_SuspiciousIncludingUpvoters: EContentReportResolution
k_EContentReportResolution_VisibilityChanged: EContentReportResolution
k_EContentReportResolution_CountryRestrictionsChanged: EContentReportResolution
k_EContentReportResolution_RemoveAndWarn: EContentReportResolution
k_EContentReportResolution_RemoveAndBan: EContentReportResolution
k_EContentReportResolution_RemoveAndKick: EContentReportResolution
k_EContentReportResolution_Sanctioned: EContentReportResolution
k_EContentReportResolution_Sustained: EContentReportResolution
k_EContentReportResolution_Broken: EContentReportResolution
k_EContentReportResolution_MAX: EContentReportResolution
k_EContentModerationSanction_Invalid: EContentModerationSanction
k_EContentModerationSanction_Deleted: EContentModerationSanction
k_EContentModerationSanction_CommunityBanned: EContentModerationSanction
k_EContentModerationSanction_HubBanned: EContentModerationSanction
k_EContentModerationSanction_TradeBanned: EContentModerationSanction
k_EContentModerationSanction_CommentHistoryDeleted: EContentModerationSanction
k_EContentModerationSanction_Relabelled: EContentModerationSanction
k_EContentModerationSanction_MarkAsSuspicious: EContentModerationSanction
k_EContentModerationSanction_Warned: EContentModerationSanction
k_EContentModerationSanction_KickedFromGroup: EContentModerationSanction
k_EContentModerationSanction_HarassmentBanned: EContentModerationSanction
k_EContentModerationSanction_HarassmentStrike: EContentModerationSanction
k_EContentModerationSanction_Escalate: EContentModerationSanction
k_EContentModerationSanction_MAX: EContentModerationSanction
k_EContentReportSubjectAction_Invalid: EContentReportSubjectAction
k_EContentReportSubjectAction_Unresolved: EContentReportSubjectAction
k_EContentReportSubjectAction_Sanctioned: EContentReportSubjectAction
k_EContentReportSubjectAction_Acquitted: EContentReportSubjectAction
k_EContentReportSubjectAction_Cancelled: EContentReportSubjectAction
k_EContentReportSubjectAction_Updated: EContentReportSubjectAction
k_EContentReportSubjectAction_Escalated: EContentReportSubjectAction
k_EContentReportSubjectAction_Disputed: EContentReportSubjectAction
k_EContentReportSubjectAction_Sustained: EContentReportSubjectAction
k_EContentReportSubjectAction_Locked: EContentReportSubjectAction
k_EContentReportSubjectAction_Unlocked: EContentReportSubjectAction
k_EContentReportSubjectAction_Deleted: EContentReportSubjectAction
k_EContentReportSubjectAction_Warned: EContentReportSubjectAction
k_EContentReportSubjectAction_BannedFromHub: EContentReportSubjectAction
k_EContentReportSubjectAction_BannedFromCommunity: EContentReportSubjectAction
k_EContentReportSubjectAction_TradeBanned: EContentReportSubjectAction
k_EContentReportSubjectAction_MarkedAsSuspicious: EContentReportSubjectAction
k_EContentReportSubjectAction_ResetContent: EContentReportSubjectAction
k_EContentReportSubjectAction_EscalatedForCSAM: EContentReportSubjectAction
k_EContentReportSubjectAction_EscalatedForTerrorism: EContentReportSubjectAction
k_EContentReportSubjectAction_Claimed: EContentReportSubjectAction
k_EContentReportSubjectAction_Released: EContentReportSubjectAction
k_EContentReportSubjectAction_PrivateMessaged: EContentReportSubjectAction
k_EContentReportSubjectAction_OwnerDisputed: EContentReportSubjectAction
k_EContentReportReason_Invalid: EContentReportReason
k_EContentReportReason_None: EContentReportReason
k_EContentReportReason_Unknown: EContentReportReason
k_EContentReportReason_Harassment: EContentReportReason
k_EContentReportReason_BullyingAndIntimidation: EContentReportReason
k_EContentReportReason_Stalking: EContentReportReason
k_EContentReportReason_Doxxing: EContentReportReason
k_EContentReportReason_OtherHarassment: EContentReportReason
k_EContentReportReason_EncouragingViolence: EContentReportReason
k_EContentReportReason_EncouragingSelfHarm: EContentReportReason
k_EContentReportReason_EncouragingSuicide: EContentReportReason
k_EContentReportReason_OtherViolenceOrSelfHarm: EContentReportReason
k_EContentReportReason_PhishingOrAccountTheft: EContentReportReason
k_EContentReportReason_AttemptedScamming: EContentReportReason
k_EContentReportReason_LinkingToMaliciousContent: EContentReportReason
k_EContentReportReason_Impersonation: EContentReportReason
k_EContentReportReason_OtherScamsAndTheft: EContentReportReason
k_EContentReportReason_EncouragingTerrorism: EContentReportReason
k_EContentReportReason_OrganizingTerrorism: EContentReportReason
k_EContentReportReason_OtherTerrorism: EContentReportReason
k_EContentReportReason_TargetedAbuse: EContentReportReason
k_EContentReportReason_NamingAndShaming: EContentReportReason
k_EContentReportReason_Discrimination: EContentReportReason
k_EContentReportReason_OtherAbuse: EContentReportReason
k_EContentReportReason_Trolling: EContentReportReason
k_EContentReportReason_Baiting: EContentReportReason
k_EContentReportReason_Derailing: EContentReportReason
k_EContentReportReason_OtherDisruptive: EContentReportReason
k_EContentReportReason_Spam: EContentReportReason
k_EContentReportReason_Begging: EContentReportReason
k_EContentReportReason_Reposting: EContentReportReason
k_EContentReportReason_OtherOffTopic: EContentReportReason
k_EContentReportReason_CSAMSexualContent: EContentReportReason
k_EContentReportReason_CSAMGroomingOrEnticement: EContentReportReason
k_EContentReportReason_CSAMOther: EContentReportReason
k_EContentReportReason_NudityOrSexualContent: EContentReportReason
k_EContentReportReason_NonConsensualMaterial: EContentReportReason
k_EContentReportReason_Advertising: EContentReportReason
k_EContentReportReason_ReferralLinks: EContentReportReason
k_EContentReportReason_Gambling: EContentReportReason
k_EContentReportReason_Raffles: EContentReportReason
k_EContentReportReason_OtherCommercialActivity: EContentReportReason
k_EContentReportReason_InauthenticReview: EContentReportReason
k_EContentReportReason_HiddenAdvertisementOrCommercialCommunication: EContentReportReason
k_EContentReportReason_MisleadingInformationAboutGoodsOrServices: EContentReportReason
k_EContentReportReason_MisleadingInformationAboutConsumerRights: EContentReportReason
k_EContentReportReason_NoncomplianceWithPricingRegulations: EContentReportReason
k_EContentReportReason_RightToBeForgottenViolation: EContentReportReason
k_EContentReportReason_MissingProcessingGroundForData: EContentReportReason
k_EContentReportReason_OtherDataProtectionAndPrivacyViolation: EContentReportReason
k_EContentReportReason_GenderedHarassment: EContentReportReason
k_EContentReportReason_GenderedBullyingAndIntimidation: EContentReportReason
k_EContentReportReason_GenderedStalking: EContentReportReason
k_EContentReportReason_GenderedDoxxing: EContentReportReason
k_EContentReportReason_GenderedOtherHarassment: EContentReportReason
k_EContentReportReason_GenderedEncouragingViolence: EContentReportReason
k_EContentReportReason_GenderedTargetedAbuse: EContentReportReason
k_EContentReportReason_CSAMFakedSexualContent: EContentReportReason
k_EContentReportReason_GenderedNonConsensualMaterial: EContentReportReason
k_EContentReportReason_FakedGenderedNonConsensualMaterial: EContentReportReason
k_EContentReportReason_FakedNonConsensualMaterial: EContentReportReason
k_EContentReportReason_NegativeEffectonDiscourseOrElections: EContentReportReason
k_EContentReportReason_QuotesModeratedContent: EContentReportReason
k_EContentReportReason_CredibleThreatOfViolence: EContentReportReason
k_EContentReportReason_AutoCreatedOnModeration: EContentReportReason
k_EContentReportReason_Piracy: EContentReportReason
k_EContentReportReason_ToSViolation: EContentReportReason
k_EContentReportReason_Miscategorized: EContentReportReason
k_EContentReportReason_BypassingProfanityFilter: EContentReportReason
k_EContentReportReason_BulkDeletion: EContentReportReason
k_EContentReportReason_MAX: EContentReportReason
k_EResolutionAutomation_Manual: EResolutionAutomation
k_EResolutionAutomation_PartiallyAutomated: EResolutionAutomation
k_EResolutionAutomation_FullyAutomated: EResolutionAutomation
k_EResolutionAutomation_MAX: EResolutionAutomation
k_EPressOutletAction_Invalid: EPressOutletAction
k_EPressOutletAction_Granted: EPressOutletAction
k_EPressOutletAction_Removed: EPressOutletAction
k_EPressOutletAction_Created: EPressOutletAction
k_EPressOutletAction_Updated: EPressOutletAction
k_EPressOutletAction_Deleted: EPressOutletAction
k_EPressOutletAction_Undeleted: EPressOutletAction
k_EPressOutletAction_StagedAdd: EPressOutletAction
k_EPressOutletAction_StagedDelete: EPressOutletAction
k_EPressOutletAction_EnterStaging: EPressOutletAction
k_EPressOutletAction_ExitStaging: EPressOutletAction
k_EPressOutletAction_ReverseStagedAdd: EPressOutletAction
k_EPressOutletAction_ReverseStagedDelete: EPressOutletAction
k_EPressOutletAction_MAX: EPressOutletAction
k_EPressOutletMemberPendingState_Member: EPressOutletMemberPendingState
k_EPressOutletMemberPendingState_StagedDelete: EPressOutletMemberPendingState
k_EPressOutletMemberPendingState_StagedAdd: EPressOutletMemberPendingState
k_EPressOutletMemberPendingState_MAX: EPressOutletMemberPendingState
k_ECommentDeleteReason_Invalid: ECommentDeleteReason
k_ECommentDeleteReason_User: ECommentDeleteReason
k_ECommentDeleteReason_ThreadOwner: ECommentDeleteReason
k_ECommentDeleteReason_Moderator: ECommentDeleteReason
k_ECommentDeleteReason_Support: ECommentDeleteReason
k_ECommentDeleteReason_Spam: ECommentDeleteReason
k_ECommentDeleteReason_AccountDeletion: ECommentDeleteReason
k_EDLCHighlightReason_None: EDLCHighlightReason
k_EDLCHighlightReason_New: EDLCHighlightReason
k_EDLCHighlightReason_ComingSoon: EDLCHighlightReason
k_EDLCHighlightReason_PlayerFavorite: EDLCHighlightReason
k_EDLCHighlightReason_Recommended: EDLCHighlightReason
k_EDLCHighlightReason_NewPlayers: EDLCHighlightReason

import launch

if not launch.is_installed("send2trash"):
    launch.run_pip("install Send2Trash", "Send2Trash requirement for image browser")

if not launch.is_installed("image-reward"):
    launch.run_pip("install image-reward", "ImageReward requirement for image browser")

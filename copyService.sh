systemctl disable controller
cp controller.service /lib/systemd/system/controller.service
chmod 644 /lib/systemd/system/controller.service
systemctl enable controller
systemctl restart controller


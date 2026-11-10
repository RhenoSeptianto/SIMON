import agent.collectors as collectors


def test_inventory_keeps_registry_values_when_frozen_powershell_output_is_empty(monkeypatch):
 monkeypatch.setattr(collectors,'registry_inventory',lambda:{'manufacturer':'ASUSTeK COMPUTER INC.','model':'ASUS EXPERTCENTER','bios_serial':'SERIAL-531','cpu':'Intel Core i3','os_name':'Windows 10 build 19045'})
 monkeypatch.setattr(collectors,'com_inventory',lambda:{})
 monkeypatch.setattr(collectors,'powershell',lambda script:{})
 result=collectors.inventory()
 assert result['manufacturer']=='ASUSTeK COMPUTER INC.'
 assert result['model']=='ASUS EXPERTCENTER'
 assert result['bios_serial']=='SERIAL-531'
 assert result['cpu']=='Intel Core i3'
 assert result['os_name']=='Windows 10 build 19045'


def test_nonempty_cim_values_override_registry_fallback(monkeypatch):
 monkeypatch.setattr(collectors,'registry_inventory',lambda:{'model':'Registry model','cpu':'Registry CPU'})
 monkeypatch.setattr(collectors,'com_inventory',lambda:{'bios_serial':'COM-SERIAL'})
 monkeypatch.setattr(collectors,'powershell',lambda script:{'model':'CIM model','cpu':'CIM CPU','manufacturer':None})
 result=collectors.inventory()
 assert result['model']=='CIM model' and result['cpu']=='CIM CPU'
 assert result['bios_serial']=='COM-SERIAL' and 'manufacturer' not in result

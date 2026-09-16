"""Offline investigation helper, not a device driver or production test suite."""
from pathlib import Path
import pefile,struct,json,hashlib,argparse
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64
from unicorn.x86_const import *
parser=argparse.ArgumentParser(description='Emulate the supplied MINI Manager decoder using synthetic data; no device I/O.')
parser.add_argument('dll', type=Path)
args=parser.parse_args()
p=args.dll
assert hashlib.sha256(p.read_bytes()).hexdigest()=='d8d87c5f3ab06d88aa2bcfc3098a129873e8445de7b15bed067d340698071fff', 'Unexpected DLL build'
pe=pefile.PE(str(p)); base=pe.OPTIONAL_HEADER.ImageBase
u=Uc(UC_ARCH_X86,UC_MODE_64); u.mem_map(base,0x20000);u.mem_write(base,pe.get_memory_mapped_image());u.mem_map(0x100000,0x10000)
stack=0x108000;vec=0x101000;stop=base+0x1000
regs=[3,2,0x1234,0x5678,300,600,1234,456,0x789a,0xbcde,0x1122,0x3344,0x5566,0x7788]
u.mem_write(vec,struct.pack('<iiQQ',1,14,14,24)+struct.pack('<14H',*regs));u.reg_write(UC_X86_REG_RSP,stack);u.reg_write(UC_X86_REG_RAX,vec)
u.emu_start(base+0x24a9,base+0x249f,count=200)
obj=stack+0x70
expected={0x00:0x33441122,0x0c:0xbcde789a,0x10:0x56781234,0x2c:0x77885566}
for off,val in expected.items(): assert struct.unpack('<I',u.mem_read(obj+off,4))[0]==val
assert struct.unpack('<4H',u.mem_read(obj+0x1c,8))[:2]==(300,600)
def getter(rva,float_result=False):
 u.reg_write(UC_X86_REG_RCX,obj);u.reg_write(UC_X86_REG_RSP,0x106000);u.mem_write(0x106000,struct.pack('<Q',stop));u.emu_start(base+rva,stop,count=200)
 if float_result:return struct.unpack('<f',struct.pack('<I',u.reg_read(UC_X86_REG_XMM0)&0xffffffff))[0]
 return u.reg_read(UC_X86_REG_RAX)
result={'vout_v':getter(0x9180,True),'iout_a':getter(0x9200,True),'temperature_k':getter(0x9280),'pump_temperature_k':getter(0x9290),'uptime_raw':getter(0x9150),'ontime_raw':getter(0x9140)}
assert abs(result['vout_v']-12.3)<1e-5 and abs(result['iout_a']-4.6)<1e-5
checks=0
for raw in [0,1,4,5,9,10,14,15,1234,3499,3500,65535]:
 u.mem_write(obj+0x16,struct.pack('<H',raw));u.mem_write(obj+0x18,struct.pack('<I',raw))
 expected_value=((raw+5)//10)/10
 for rva in [0x9180,0x9200]:assert abs(getter(rva,True)-expected_value)<0.001;checks+=1
result['rounding_boundary_checks']=checks;result['method']='Unicorn emulation of original DLL instructions, synthetic register data, no OS calls or device connection';result['dll_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps(result,indent=2))

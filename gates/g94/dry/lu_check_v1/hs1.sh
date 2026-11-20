# One 5 ms slot of the 3d stack through HotSpot; prints HotSpot's own peak RSS (VmHWM) every 10 s and its exit.
# Peak RSS is sampled every 10 s, so a short peak at the end can be missed; completion under the cap is the check.
rm -rf /tmp/w
python -c "
import sys,os; sys.path[:0]=['.','gates/g94']
import cases
from opentsense.stack import model, to_hotspot
st=model.load(os.path.join('configs','stacks',cases.STACKS['3d'][0]))
to_hotspot.write(st,cases.step('3d',1,${1:-1}),'/tmp/w',transient=(0.005,0.005))
" || { echo "setup failed"; exit 1; }
cd /tmp/w && s=$(date +%s)
/opt/hotspot/hotspot -c hotspot.config -p power.ptrace -grid_layer_file stack.lcf -model_type grid -detailed_3D on -o o.ttrace -grid_transient_file o.grid > out.txt 2>&1 &
p=$!
while kill -0 $p 2>/dev/null; do sleep 10; echo "t=$(( $(date +%s)-s )) $(grep -E 'VmHWM|VmRSS|VmSwap' /proc/$p/status 2>/dev/null | tr -s ' \n' ' ') grid_lines=$(wc -l < o.grid 2>/dev/null)"; done
wait $p; echo rc=$? secs=$(( $(date +%s)-s ))
